from __future__ import annotations
import traceback
from pathlib import Path
from typing import Callable
from playwright.sync_api import Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright
from .config import RobotConfig, ConfigError
from .io_utils import atomic_json_write, now_iso, sanitize, sha256_file
from .models import JobRequest, JobValidationError, RobotEvent, RobotResult

StatusCallback = Callable[[RobotEvent], None]

class RobotExecutionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

class ExecutionContext:
    def __init__(self, job: JobRequest, config: RobotConfig, callback: StatusCallback | None = None):
        self.job = job
        self.config = config
        self.callback = callback
        self.dir = job.download_dir.resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.dir / "robot.log"
        self.status_path = self.dir / "status.json"
        self.result_path = self.dir / "result.json"
        self.messages: list[str] = []

    def log(self, message: object) -> None:
        safe = sanitize(message, self.config.secrets)
        line = f"{now_iso()} | {safe}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def add_message(self, message: str) -> None:
        safe = sanitize(message, self.config.secrets)
        self.messages.append(safe)
        self.log(safe)

    def emit(self, state: str, detail: str | None = None) -> RobotEvent:
        safe_detail = sanitize(detail, self.config.secrets) if detail else None
        event = RobotEvent(self.job.execution_id, state, now_iso(), safe_detail)
        atomic_json_write(self.status_path, event.to_dict())
        self.log(f"STATUS={state}" + (f" | {safe_detail}" if safe_detail else ""))
        if self.callback:
            self.callback(event)
        return event

    def save_result(self, result: RobotResult) -> None:
        atomic_json_write(self.result_path, result.to_dict())

def _ssw_date(value) -> str:
    return value.strftime("%d%m%y")

def _sanitize_evidence_page(page) -> None:
    for selector in ('[id="1"]', '[id="2"]', '[id="3"]', '[id="4"]'):
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                locator.first.fill("")
        except Exception:
            pass

def _capture_evidence(page, ctx: ExecutionContext, name: str) -> None:
    try:
        _sanitize_evidence_page(page)
        page.screenshot(path=str(ctx.dir / f"evidence_{name}.png"), full_page=True)
    except Exception as exc:
        ctx.log(f"Não foi possível gerar evidência {name}: {exc}")

def _execute_browser(playwright: Playwright, ctx: ExecutionContext) -> Path:
    cfg = ctx.config
    job = ctx.job
    browser = context = page = page036 = None
    try:
        ctx.emit("ROBOT_STARTING", "Executor recebeu a tarefa.")
        browser = playwright.chromium.launch(headless=cfg.headless, slow_mo=cfg.slow_mo)
        context = browser.new_context(accept_downloads=True)
        context.set_default_timeout(cfg.action_timeout_ms)
        page = context.new_page()

        ctx.emit("AUTHENTICATING", "Acessando o SSW e realizando login.")
        page.goto(cfg.ssw_url, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        page.locator('[id="1"]').fill(cfg.company)
        page.locator('[id="2"]').fill(cfg.cpf)
        page.locator('[id="3"]').fill(cfg.username)
        page.locator('[id="4"]').fill(cfg.password)
        page.wait_for_timeout(700)
        page.get_by_role("link", name="►").click()
        page.wait_for_timeout(2000)

        campo_opcao = page.locator('[id="3"]')
        campo_opcao.fill(cfg.option)
        page.wait_for_timeout(600)
        try:
            with page.expect_popup(timeout=cfg.action_timeout_ms) as popup_info:
                campo_opcao.press("Enter")
            page036 = popup_info.value
        except PlaywrightTimeoutError as exc:
            _capture_evidence(page, ctx, "auth_or_option_036")
            raise RobotExecutionError(
                "AUTH_OR_OPTION_TIMEOUT",
                "Não foi possível abrir a opção 036. Verifique login, sessão ou alteração na tela do SSW.",
            ) from exc

        page036.wait_for_load_state("domcontentloaded")
        page036.wait_for_timeout(1500)
        ctx.add_message("Login OK")
        ctx.add_message("Opção 036 aberta")

        page036.locator("#t_excel").fill("S")
        page036.locator("#t_unidade").fill(job.unit)
        page036.locator("#t_dt_ini").fill(_ssw_date(job.start_date))
        page036.locator("#t_dt_fin").fill(_ssw_date(job.end_date))
        page036.wait_for_timeout(800)

        ctx.emit(
            "REQUESTING_REPORT",
            f"Opção 036: {job.start_date.isoformat()} a {job.end_date.isoformat()} / unidade {job.unit}.",
        )
        ctx.emit("WAITING_DOWNLOAD", "Relatório solicitado; aguardando o download do SSW.")

        try:
            with page036.expect_download(timeout=cfg.download_timeout_ms) as download_info:
                page036.locator("#btn_env_periodo").click()
            download = download_info.value
        except PlaywrightTimeoutError as exc:
            _capture_evidence(page036, ctx, "download_timeout")
            raise RobotExecutionError(
                "DOWNLOAD_TIMEOUT",
                "O SSW não iniciou o download dentro do tempo configurado.",
            ) from exc

        suggested = download.suggested_filename or "relatorio.sswweb"
        extension = Path(suggested).suffix or ".sswweb"
        final_path = ctx.dir / f"relatorio_036{extension}"
        download.save_as(str(final_path))

        failure = download.failure()
        if failure:
            raise RobotExecutionError("DOWNLOAD_FAILED", f"O navegador informou falha no download: {failure}")
        if not final_path.exists():
            raise RobotExecutionError("FILE_NOT_FOUND", "O download terminou, mas o arquivo não foi encontrado.")
        if final_path.stat().st_size <= 0:
            raise RobotExecutionError("EMPTY_DOWNLOAD", "O arquivo baixado está vazio.")

        ctx.add_message("Relatório gerado")
        ctx.add_message("Download concluído")
        ctx.emit("DOWNLOADED", f"Arquivo salvo: {final_path}")
        return final_path

    except RobotExecutionError:
        raise
    except PlaywrightTimeoutError as exc:
        if page036 is not None:
            _capture_evidence(page036, ctx, "selector_timeout")
        elif page is not None:
            _capture_evidence(page, ctx, "selector_timeout")
        raise RobotExecutionError(
            "SELECTOR_TIMEOUT",
            "Uma etapa da interface do SSW não respondeu no tempo esperado. Pode haver alteração de tela/seletor.",
        ) from exc
    except Exception as exc:
        if page036 is not None:
            _capture_evidence(page036, ctx, "unexpected")
        elif page is not None:
            _capture_evidence(page, ctx, "unexpected")
        raise RobotExecutionError("ROBOT_UNEXPECTED", f"Falha inesperada do executor: {exc}") from exc
    finally:
        if context is not None:
            try: context.close()
            except Exception: pass
        if browser is not None:
            try: browser.close()
            except Exception: pass

def run_job(payload: dict, *, status_callback: StatusCallback | None = None, config: RobotConfig | None = None) -> dict:
    """API principal de integração. O robô não grava no PostgreSQL operacional."""
    started_at = now_iso()
    try:
        cfg = config or RobotConfig.from_env()
    except ConfigError as exc:
        return RobotResult(
            execution_id=str(payload.get("execution_id") or "UNKNOWN"),
            robot_status="ERROR", started_at=started_at, finished_at=now_iso(),
            error_code="CONFIG_ERROR", error_message=str(exc),
        ).to_dict()

    try:
        job = JobRequest.from_dict(payload, cfg)
    except JobValidationError as exc:
        return RobotResult(
            execution_id=str(payload.get("execution_id") or "UNKNOWN"),
            robot_status="ERROR", started_at=started_at, finished_at=now_iso(),
            error_code="INVALID_JOB", error_message=str(exc),
        ).to_dict()

    ctx = ExecutionContext(job, cfg, status_callback)
    ctx.log(
        "JOB recebido | "
        f"execution_id={job.execution_id} | report_type={job.report_type} | "
        f"start_date={job.start_date.isoformat()} | end_date={job.end_date.isoformat()} | "
        f"unit={job.unit} | mode={job.mode} | requested_by={job.requested_by}"
    )
    result = RobotResult(job.execution_id, "ERROR", started_at)

    try:
        with sync_playwright() as playwright:
            file_path = _execute_browser(playwright, ctx)
        result.robot_status = "DOWNLOADED"
        result.finished_at = now_iso()
        result.file_path = str(file_path)
        result.file_size = file_path.stat().st_size
        result.sha256 = sha256_file(file_path)
        result.messages = list(ctx.messages)
        ctx.save_result(result)
        return result.to_dict()
    except RobotExecutionError as exc:
        safe_message = sanitize(exc.message, cfg.secrets)
        ctx.emit("ERROR", safe_message)
        ctx.add_message(f"ERRO {exc.code}: {safe_message}")
        result.finished_at = now_iso()
        result.messages = list(ctx.messages)
        result.error_code = exc.code
        result.error_message = safe_message
        ctx.save_result(result)
        return result.to_dict()
    except Exception as exc:
        safe_message = sanitize(str(exc), cfg.secrets)
        ctx.emit("ERROR", safe_message)
        ctx.log(traceback.format_exc())
        result.finished_at = now_iso()
        result.messages = list(ctx.messages)
        result.error_code = "UNHANDLED_ERROR"
        result.error_message = safe_message
        ctx.save_result(result)
        return result.to_dict()
