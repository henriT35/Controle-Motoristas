from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import importlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Callable

from django.conf import settings
from django.utils import timezone

from .models import ImportRun, ImportStep

logger = logging.getLogger("painel.ssw.robot")

BRIDGE_BUILD = "0.2.2-p13.6"
ROBOT_ALIAS = "painel_ssw_homologated"
CORE_FILES = (
    "robot_ssw/__init__.py",
    "robot_ssw/config.py",
    "robot_ssw/io_utils.py",
    "robot_ssw/models.py",
    "robot_ssw/worker.py",
    "robot_ssw/cli.py",
)


class RobotBridgeError(RuntimeError):
    def __init__(self, message: str, *, code: str = "ROBOT_ERROR"):
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class RobotArtifact:
    path: Path
    size: int
    sha256: str
    result: dict[str, Any]


def robot_root() -> Path:
    configured = getattr(settings, "SSW_ROBOT_DIR", "")
    return Path(configured).expanduser().resolve() if configured else (settings.BASE_DIR / "robot_ssw").resolve()


def execution_id_for(run: ImportRun) -> str:
    if run.created_at:
        stamp = timezone.localtime(run.created_at).strftime("%Y%m%d-%H%M%S")
    else:
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    return f"SSW-{stamp}-{run.pk:06d}"


def execution_dir_for(run: ImportRun) -> Path:
    path = (settings.BASE_DIR / "imports" / "inbox" / execution_id_for(run)).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_robot_payload(run: ImportRun) -> tuple[dict[str, Any], Path]:
    execution_dir = execution_dir_for(run)
    payload = {
        "execution_id": execution_id_for(run),
        "start_date": run.start_date.isoformat(),
        "end_date": run.end_date.isoformat(),
        "mode": run.kind,
        "requested_by": getattr(run.requested_by, "username", None) or "system",
        "report_type": getattr(settings, "SSW_ROBOT_REPORT_TYPE", "ROMANEIOS_036"),
        "unit": getattr(settings, "SSW_ROBOT_UNIT", "BEL"),
        "download_dir": str(execution_dir),
    }
    # task.json é somente rastreabilidade. Nunca contém credenciais.
    (execution_dir / "task.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload, execution_dir


def _install_resilient_core_json_writer() -> None:
    """Protege status.json/result.json sem alterar o core homologado no disco.

    O core P13 continua byte a byte intacto. Em runtime substituímos somente a
    referência da função de escrita JSON já importada pelo módulo worker.
    ``status.json`` é telemetria e nunca pode abortar a automação por WinError 5.
    ``result.json`` continua obrigatório, porém ganha temporário exclusivo e retry.
    """
    from apps.ssw.safe_json import resilient_atomic_json_write

    io_module = importlib.import_module(f"{ROBOT_ALIAS}.io_utils")
    worker_module = importlib.import_module(f"{ROBOT_ALIAS}.worker")

    existing = getattr(worker_module, "atomic_json_write", None)
    if getattr(existing, "_painel_v0306_resilient", False):
        return

    def protected_write(path: Path, payload: dict[str, Any]) -> None:
        target = Path(path)
        telemetry_only = target.name.lower() == "status.json"
        ok = resilient_atomic_json_write(
            target,
            payload,
            best_effort=telemetry_only,
            retries=12,
            base_delay=0.05,
            max_delay=0.50,
            indent=2,
        )
        if telemetry_only and not ok:
            # Não inclui payload/credenciais. O evento serve só para diagnóstico.
            logger.warning(
                "Falha definitiva ao atualizar telemetria %s; execução continuará.",
                target,
            )
            try:
                warning_path = target.parent / "telemetry_write_warnings.log"
                with warning_path.open("a", encoding="utf-8", errors="replace") as handle:
                    handle.write(
                        f"{timezone.now().isoformat()} | STATUS_WRITE_SKIPPED | "
                        f"path={target.name} | execution_continued=true\n"
                    )
            except Exception:
                pass

    setattr(protected_write, "_painel_v0306_resilient", True)
    io_module.atomic_json_write = protected_write
    worker_module.atomic_json_write = protected_write


def _load_homologated_package():
    root = robot_root()
    package_dir = root / "robot_ssw"
    init_py = package_dir / "__init__.py"
    if not init_py.exists():
        raise RobotBridgeError(
            f"Core homologado não encontrado: {init_py}", code="ROBOT_CORE_NOT_FOUND"
        )

    existing = sys.modules.get(ROBOT_ALIAS)
    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(
        ROBOT_ALIAS,
        init_py,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise RobotBridgeError("Não foi possível carregar o pacote homologado do robô.", code="ROBOT_IMPORT_ERROR")
    module = importlib.util.module_from_spec(spec)
    sys.modules[ROBOT_ALIAS] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(ROBOT_ALIAS, None)
        raise
    return module


def _load_robot_env(*, override: bool = True) -> Path:
    root = robot_root()
    env_path = root / ".env"
    if not env_path.exists():
        raise RobotBridgeError(
            f"Configuração do robô não encontrada: {env_path}. Execute CONFIGURAR_CREDENCIAIS_SSW.bat.",
            code="CONFIG_ERROR",
        )
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RobotBridgeError(
            "Dependência python-dotenv ausente. Execute PREPARAR_ROBO_HOMOLOGADO.bat.",
            code="ROBOT_DEPENDENCY_MISSING",
        ) from exc
    load_dotenv(dotenv_path=env_path, override=override)
    return env_path


def _config_class():
    _load_homologated_package()
    return importlib.import_module(f"{ROBOT_ALIAS}.config").RobotConfig


def _core_hashes_ok() -> tuple[bool, str]:
    root = robot_root()
    manifest = root / "HOMOLOGATED_CORE.sha256"
    if not manifest.exists():
        return False, "Manifesto HOMOLOGATED_CORE.sha256 ausente."
    expected: dict[str, str] = {}
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        parts = raw.strip().split(maxsplit=1)
        if len(parts) == 2:
            expected[parts[1].lstrip("*")] = parts[0].lower()
    for rel in CORE_FILES:
        path = root / rel
        if not path.exists():
            return False, f"Arquivo do core ausente: {rel}"
        digest = sha256(path.read_bytes()).hexdigest().lower()
        expected_digest = expected.get(rel)
        if expected_digest and digest != expected_digest:
            return False, f"Core homologado alterado: {rel}"
    return True, "Core homologado íntegro."


def check_robot_ready(*, launch_browser: bool = True) -> tuple[bool, str]:
    """Preflight sem login real no SSW.

    Valida core, API run_job, .env, Playwright, Chromium e pasta de saída.
    """
    if not getattr(settings, "SSW_ROBOT_ENABLED", False):
        return False, "Robô desabilitado (SSW_ROBOT_ENABLED=0)."

    root = robot_root()
    if not root.exists():
        return False, f"Pasta do robô não encontrada: {root}"

    ok, detail = _core_hashes_ok()
    if not ok:
        return False, detail

    try:
        package = _load_homologated_package()
    except Exception as exc:
        return False, f"Falha ao importar core homologado: {exc}"
    if not callable(getattr(package, "run_job", None)):
        return False, "API robot_ssw.run_job não encontrada."

    env_path = root / ".env"
    if not env_path.exists():
        return False, f"Configuração do robô não encontrada: {env_path}"
    env_values: dict[str, str] = {}
    try:
        # IMPORTANTE: o configurador homologado grava valores entre aspas para
        # preservar senhas/caracteres especiais. Ler o .env manualmente faria
        # SSW_OPTION="036" virar literalmente '"036"' e quebraria o preflight.
        # Use o mesmo parser dotenv que o core homologado usa em runtime.
        from dotenv import dotenv_values

        parsed = dotenv_values(dotenv_path=env_path, encoding="utf-8-sig")
        env_values = {
            str(key).strip(): str(value).strip()
            for key, value in parsed.items()
            if key is not None and value is not None
        }
    except ImportError:
        # Fallback defensivo para diagnóstico antes da preparação das dependências.
        try:
            for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                env_values[key.strip()] = value
        except Exception as exc:
            return False, f"Não foi possível ler .env do robô: {exc}"
    except Exception as exc:
        return False, f"Não foi possível interpretar .env do robô: {exc}"
    missing = [name for name in ("SSW_EMPRESA", "SSW_CPF", "SSW_USUARIO", "SSW_SENHA") if not env_values.get(name)]
    if missing:
        return False, "Configuração SSW incompleta: " + ", ".join(missing)
    option = str(env_values.get("SSW_OPTION", "036") or "036").strip().strip('"').strip("'")
    expected_unit = str(getattr(settings, "SSW_ROBOT_UNIT", "BEL") or "BEL").strip().upper()
    unit = str(env_values.get("SSW_UNIT", expected_unit) or expected_unit).strip().strip('"').strip("'").upper()
    if option != "036":
        return False, f"Opção do robô divergente: {option}; esperado 036."
    if unit != expected_unit:
        return False, f"Unidade padrão divergente: {unit}; esperado {expected_unit}."

    inbox = settings.BASE_DIR / "imports" / "inbox"
    try:
        inbox.mkdir(parents=True, exist_ok=True)
        probe = inbox / ".p13_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as exc:
        return False, f"Pasta de saída sem permissão de escrita: {exc}"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "Playwright não instalado. Execute PREPARAR_ROBO_HOMOLOGADO.bat."

    if launch_browser:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
        except Exception as exc:
            return False, f"Chromium do Playwright não conseguiu iniciar: {exc}"

    return True, "Core homologado íntegro; run_job, configuração, Playwright e Chromium prontos."


def _validate_download(result: dict[str, Any], execution_dir: Path) -> RobotArtifact:
    status = str(result.get("robot_status") or "").upper()
    if status != "DOWNLOADED":
        raise RobotBridgeError(
            str(result.get("error_message") or "O robô não concluiu o download."),
            code=str(result.get("error_code") or "ROBOT_FAILED"),
        )

    raw_path = result.get("file_path")
    if not raw_path:
        raise RobotBridgeError("DOWNLOADED sem file_path no resultado do robô.", code="FILE_NOT_FOUND")
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = execution_dir / path
    path = path.resolve()
    try:
        path.relative_to(execution_dir.resolve())
    except ValueError as exc:
        raise RobotBridgeError(
            "O robô devolveu arquivo fora da pasta isolada da execução.", code="ROBOT_OUTPUT_OUTSIDE_EXECUTION"
        ) from exc
    if not path.exists() or not path.is_file():
        raise RobotBridgeError("Arquivo informado pelo robô não existe.", code="FILE_NOT_FOUND")
    size = path.stat().st_size
    if size <= 0:
        raise RobotBridgeError("Arquivo baixado está vazio.", code="EMPTY_DOWNLOAD")
    digest = sha256(path.read_bytes()).hexdigest()
    reported = str(result.get("sha256") or "").lower()
    if reported and reported != digest.lower():
        raise RobotBridgeError("SHA-256 devolvido pelo robô não confere com o arquivo.", code="ROBOT_HASH_MISMATCH")
    return RobotArtifact(path=path, size=size, sha256=digest, result=result)


def run_homologated_robot(run: ImportRun, *, status_callback: Callable[[Any], None] | None = None) -> RobotArtifact:
    ready, detail = check_robot_ready(launch_browser=False)
    if not ready:
        raise RobotBridgeError(detail, code="ROBOT_NOT_READY")

    payload, execution_dir = build_robot_payload(run)
    _load_robot_env(override=True)
    package = _load_homologated_package()
    _install_resilient_core_json_writer()

    logger.info("Chamando robot_ssw.run_job execution_id=%s", payload["execution_id"])
    try:
        result = package.run_job(payload, status_callback=status_callback)
    except Exception as exc:
        raise RobotBridgeError(f"Falha ao chamar run_job: {exc}", code="ROBOT_UNEXPECTED") from exc
    if not isinstance(result, dict):
        raise RobotBridgeError("run_job devolveu resultado inválido.", code="ROBOT_RESULT_INVALID")
    return _validate_download(result, execution_dir)


def upsert_step(run: ImportRun, name: str, status: str, message: str = "") -> ImportStep:
    step = run.steps.filter(name=name).order_by("id").first()
    if step is None:
        step = ImportStep.objects.create(run=run, name=name)
    step.status = status
    step.occurred_at = timezone.now()
    step.message = (message or "")[:4000]
    step.save(update_fields=["status", "occurred_at", "message"])
    return step
