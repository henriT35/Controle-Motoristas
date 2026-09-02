from __future__ import annotations

import json
import os
import platform
import re
import socket
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|senha|token|cookie|authorization|secret)(\s*[:=]\s*)([^\s,;]+)"),
]

DIAGNOSTIC_FILES = {
    "events.jsonl",
    "orchestrator.log",
    "worker_process.log",
    "worker_state.json",
    "robot.log",
    "status.json",
    "result.json",
    "diagnostic.json",
    "traceback.txt",
    "environment.json",
    "task.json",
}


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def sanitize(value: Any) -> Any:
    """Sanitização defensiva: diagnóstico nunca deve expor credenciais."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            k = str(key)
            if k.lower() in {"password", "senha", "token", "cookie", "authorization", "secret"}:
                out[k] = "***"
            else:
                out[k] = sanitize(item)
        return out
    if isinstance(value, (list, tuple, set)):
        return [sanitize(v) for v in value]
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return text


def safe_json_load(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def atomic_json_write(path: Path, payload: dict[str, Any]) -> bool:
    """Escrita resiliente de artefatos de diagnóstico.

    Diagnóstico/heartbeat são observabilidade: bloqueios transitórios de arquivo
    no Windows nunca podem derrubar o worker nem o watchdog.
    """
    from apps.ssw.safe_json import resilient_atomic_json_write

    return resilient_atomic_json_write(
        path,
        payload,
        transform=sanitize,
        best_effort=True,
        retries=12,
        base_delay=0.05,
        max_delay=0.50,
        indent=2,
    )


def _append_line(path: Path, line: str) -> bool:
    """Append de diagnóstico best-effort; nunca interrompe o watchdog."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    for attempt in range(6):
        try:
            with path.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(line.rstrip("\n") + "\n")
            return True
        except OSError:
            if attempt >= 5:
                return False
            time.sleep(min(0.25, 0.025 * (2 ** attempt)))
        except Exception:
            return False
    return False


@dataclass(slots=True)
class RunContext:
    execution_id: str
    run_pk: str
    batch_id: str | None = None
    attempt: int = 1
    start_date: str | None = None
    end_date: str | None = None
    app_version: str | None = None


class DiagnosticRecorder:
    def __init__(self, run_dir: Path, context: RunContext):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.context = context
        self.events_path = self.run_dir / "events.jsonl"
        self.human_log_path = self.run_dir / "orchestrator.log"
        self.diagnostic_path = self.run_dir / "diagnostic.json"
        self.environment_path = self.run_dir / "environment.json"
        self.last_progress_at: str | None = None
        self._lock = threading.Lock()
        self.write_environment()

    def _base(self) -> dict[str, Any]:
        return {
            "timestamp": iso_now(),
            "execution_id": self.context.execution_id,
            "run_pk": self.context.run_pk,
            "batch_id": self.context.batch_id,
            "attempt": self.context.attempt,
            "start_date": self.context.start_date,
            "end_date": self.context.end_date,
            "app_version": self.context.app_version,
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "thread": threading.current_thread().name,
        }

    def event(
        self,
        event: str,
        *,
        level: str = "INFO",
        stage: str | None = None,
        message: str | None = None,
        progress: bool = True,
        **extra: Any,
    ) -> None:
        payload = self._base()
        payload.update(
            {
                "level": level.upper(),
                "event": event,
                "component": "ssw_orchestrator",
                "stage": stage,
                "message": sanitize(message),
            }
        )
        payload.update(sanitize(extra) or {})
        if progress:
            self.last_progress_at = payload["timestamp"]
        payload["last_progress_at"] = self.last_progress_at
        safe = sanitize(payload)
        encoded = json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
        human = (
            f"{safe['timestamp']} | {safe['level']:<8} | {event}"
            + (f" | stage={stage}" if stage else "")
            + (f" | {safe['message']}" if safe.get("message") else "")
        )
        with self._lock:
            _append_line(self.events_path, encoded)
            _append_line(self.human_log_path, human)

    def diagnostic(self, **payload: Any) -> None:
        data = self._base()
        data.update(payload)
        data["last_progress_at"] = self.last_progress_at
        atomic_json_write(self.diagnostic_path, data)

    def write_environment(self) -> None:
        payload = {
            "captured_at": iso_now(),
            "execution_id": self.context.execution_id,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": sys.version,
            "python_executable": sys.executable,
            "app_version": self.context.app_version,
        }
        try:
            from apps.ssw.robot_bridge import BRIDGE_BUILD
            from apps.ssw.robot_service import SERVICE_BUILD

            payload["bridge_build"] = BRIDGE_BUILD
            payload["robot_service_build"] = SERVICE_BUILD
        except Exception:
            pass
        atomic_json_write(self.environment_path, payload)


def resolve_execution_dir(base_dir: Path, execution_id: str) -> Path:
    candidates = [
        base_dir / "imports" / "inbox" / execution_id,
        base_dir / "local_data" / "ssw_runs" / execution_id,
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def read_robot_stage(run_dir: Path) -> tuple[str | None, dict[str, Any]]:
    status = safe_json_load(run_dir / "status.json")
    stage = status.get("state") or status.get("status") or status.get("robot_status") or status.get("stage")
    return (str(stage) if stage else None, status)


def pause_marker_path(base_dir: Path) -> Path:
    return base_dir / "local_data" / "ssw_queue_paused.json"


def pause_queue(base_dir: Path, *, reason: str, execution_id: str, error_code: str) -> None:
    atomic_json_write(
        pause_marker_path(base_dir),
        {
            "paused": True,
            "paused_at": iso_now(),
            "reason": sanitize(reason),
            "execution_id": execution_id,
            "error_code": error_code,
        },
    )


def resume_queue(base_dir: Path) -> None:
    pause_marker_path(base_dir).unlink(missing_ok=True)


def queue_pause_state(base_dir: Path) -> dict[str, Any]:
    return safe_json_load(pause_marker_path(base_dir))


def worker_state_path(run_dir: Path) -> Path:
    return run_dir / "worker_state.json"


def write_worker_state(run_dir: Path, **payload: Any) -> None:
    current = safe_json_load(worker_state_path(run_dir))
    current.update(payload)
    current["updated_at"] = iso_now()
    atomic_json_write(worker_state_path(run_dir), current)


def read_worker_state(run_dir: Path) -> dict[str, Any]:
    return safe_json_load(worker_state_path(run_dir))


def model_field_names(instance: Any) -> set[str]:
    try:
        return {f.name for f in instance._meta.get_fields() if getattr(f, "concrete", False)}
    except Exception:
        return set()


def first_attr(obj: Any, names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if value not in (None, ""):
            return value
    return default


def mark_run_error(run: Any, *, error_code: str, message: str) -> None:
    """Atualiza apenas ImportRun; nunca toca tabelas operacionais de entregas."""
    fields = model_field_names(run)
    changed: list[str] = []

    if "status" in fields:
        run.status = "ERROR"
        changed.append("status")
    if "error_count" in fields:
        run.error_count = max(int(getattr(run, "error_count", 0) or 0), 1)
        changed.append("error_count")
    if "error_code" in fields:
        run.error_code = error_code
        changed.append("error_code")
    if "error_message" in fields:
        run.error_message = sanitize(message)
        changed.append("error_message")
    elif "message" in fields:
        run.message = sanitize(f"{error_code}: {message}")[:4000]
        changed.append("message")

    for name in ("finished_at", "completed_at", "ended_at"):
        if name in fields:
            try:
                from django.utils import timezone as dj_timezone

                setattr(run, name, dj_timezone.now())
                changed.append(name)
            except Exception:
                pass

    if changed:
        run.save(update_fields=list(dict.fromkeys(changed)))


def mark_run_queued(run: Any, *, message: str) -> None:
    fields = model_field_names(run)
    changed: list[str] = []
    if "status" in fields:
        run.status = "QUEUED"
        changed.append("status")
    if "message" in fields:
        run.message = sanitize(message)[:4000]
        changed.append("message")
    if changed:
        run.save(update_fields=changed)


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def pid_alive(pid: Any) -> bool:
    try:
        pid_int = int(pid)
    except Exception:
        return False
    if pid_int <= 0:
        return False
    if os.name == "nt":
        try:
            proc = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_int}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return f'"{pid_int}"' in proc.stdout or f",{pid_int}," in proc.stdout
        except Exception:
            return False
    try:
        os.kill(pid_int, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def reconcile_orphan_runs(base_dir: Path, *, hard_timeout: int | None = None, grace_seconds: int | None = None) -> list[int]:
    """Finaliza execuções que perderam o executor/watchdog.

    Há quatro relógios diferentes e eles NÃO podem ser confundidos:

    * DISPATCH: Popen foi solicitado, mas nenhum heartbeat apareceu;
    * ROBOT: o robô está executando dentro do watchdog;
    * IMPORT: protegido pelo próprio watchdog após DOWNLOADED;
    * HEARTBEAT: um processo que deveria estar vivo deixou de sinalizar.

    A rotina é idempotente e pode ser chamada pelo polling da UI, pelo dispatcher e
    por comando administrativo. Assim uma fila não depende de "alguém clicar em
    executar de novo" para descobrir um processo morto.
    """
    from django.conf import settings
    from django.utils import timezone

    from apps.ssw.models import ImportRun
    from apps.ssw.robot_bridge import execution_id_for, upsert_step

    robot_timeout = int(hard_timeout or getattr(settings, "SSW_ROBOT_TIMEOUT_SECONDS", 900))
    dispatch_timeout = int(getattr(settings, "SSW_ROBOT_DISPATCH_TIMEOUT_SECONDS", 90))
    grace = int(grace_seconds or getattr(settings, "SSW_ROBOT_ORPHAN_GRACE_SECONDS", 120))
    heartbeat = int(getattr(settings, "SSW_ROBOT_HEARTBEAT_SECONDS", 10))
    heartbeat_lost = int(getattr(settings, "SSW_ROBOT_HEARTBEAT_LOST_SECONDS", max(45, heartbeat * 4)))
    now = timezone.now()
    recovered: list[int] = []

    active = ImportRun.objects.filter(status__in=[ImportRun.Status.DISPATCHED, ImportRun.Status.RUNNING])
    for run in active:
        execution_id = execution_id_for(run)
        run_dir = resolve_execution_dir(base_dir, execution_id)
        state = read_worker_state(run_dir)
        hb = _parse_iso(state.get("last_heartbeat_at") or state.get("updated_at")) if state else None

        dispatch_at = (
            run.steps.filter(name="Despacho")
            .exclude(occurred_at=None)
            .order_by("-occurred_at", "-id")
            .values_list("occurred_at", flat=True)
            .first()
        )
        reference = hb or run.started_at or dispatch_at or run.created_at
        age = max((now - reference).total_seconds(), 0) if reference else robot_timeout + grace + 1

        watchdog_alive = pid_alive(state.get("watchdog_pid")) if state else False
        child_alive = pid_alive(state.get("child_pid")) if state else False
        process_alive = watchdog_alive or child_alive

        error_code = None
        probable_cause = None
        failed_stage = str(state.get("stage") or run.status) if state else str(run.status)

        # Caso que originou BUG-001: Popen foi pedido, mas o subprocesso nunca
        # chegou a escrever worker_state/heartbeat. O código antigo esperava o
        # timeout completo do robô (15min + folga) e, pior, só reconciliava quando
        # outro despacho ocorria. Agora o polling também chama esta rotina.
        if run.status == ImportRun.Status.DISPATCHED and not state:
            dispatch_age = max((now - (dispatch_at or run.created_at)).total_seconds(), 0)
            if dispatch_age > dispatch_timeout:
                error_code = "ROBOT_DISPATCH_TIMEOUT"
                probable_cause = (
                    f"O executor não assumiu a tarefa em {int(dispatch_age)}s "
                    f"(limite {dispatch_timeout}s)."
                )
                failed_stage = "DISPATCHED"

        if not error_code and state:
            terminal_state = str(state.get("status") or "").upper() in {
                "ERROR", "COMPLETED", "TIMEOUT_TERMINATING", "NOT_STARTED_QUEUE_PAUSED"
            }
            if terminal_state and run.status in {ImportRun.Status.DISPATCHED, ImportRun.Status.RUNNING} and age > max(grace, heartbeat * 3):
                error_code = "ORPHAN_RUNNING_JOB"
                probable_cause = "O worker terminou, mas o ImportRun permaneceu ativo no banco."
            elif not process_alive and age > max(grace, heartbeat * 3):
                error_code = "WORKER_PROCESS_LOST"
                probable_cause = "O PID do watchdog/worker não existe mais e não houve finalização do ImportRun."
            elif process_alive and hb and age > heartbeat_lost:
                error_code = "WORKER_HEARTBEAT_LOST"
                probable_cause = (
                    f"O processo ainda existe, porém não atualiza heartbeat há {int(age)}s "
                    f"(limite {heartbeat_lost}s)."
                )

        # Compatibilidade com execuções legadas sem worker_state nem etapa de
        # despacho: somente após timeout completo + folga.
        if not error_code and not state and run.status == ImportRun.Status.RUNNING and age > robot_timeout + grace:
            error_code = "ORPHAN_RUNNING_JOB"
            probable_cause = f"Execução RUNNING legada ficou {int(age)}s sem estado do worker."

        if not error_code:
            continue

        message = f"{probable_cause} Execução encerrada automaticamente para liberar a fila."
        mark_run_error(run, error_code=error_code, message=message)
        try:
            upsert_step(run, "Watchdog", "ERROR", f"{error_code}: {message}")
        except Exception:
            pass
        pause_queue(
            base_dir,
            reason=message,
            execution_id=execution_id,
            error_code=error_code,
        )
        rec = DiagnosticRecorder(
            run_dir,
            RunContext(
                execution_id=execution_id,
                run_pk=str(run.pk),
                start_date=str(run.start_date),
                end_date=str(run.end_date),
                app_version=_read_version(base_dir),
            ),
        )
        rec.event(
            error_code,
            level="ERROR",
            stage=failed_stage,
            message=message,
            state=state,
            age_seconds=age,
            process_alive=process_alive,
            watchdog_alive=watchdog_alive,
            child_alive=child_alive,
            error_code=error_code,
        )
        rec.diagnostic(
            result="ERROR",
            error_code=error_code,
            failed_component="robot_worker",
            failed_stage=failed_stage,
            retryable=True,
            queue_paused=True,
            probable_cause=probable_cause,
            recommended_action="Confirmar o executor/SSW disponível, retomar a fila e reprocessar somente esta janela.",
        )
        recovered.append(run.pk)
    return recovered

def _read_version(base_dir: Path) -> str:
    try:
        return (base_dir / "VERSION.txt").read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


def build_diagnostic_zip(base_dir: Path, execution_id: str) -> Path:
    run_dir = resolve_execution_dir(base_dir, execution_id)
    if not run_dir.exists():
        raise FileNotFoundError(f"Pasta da execução não encontrada: {run_dir}")

    output_dir = base_dir / "local_data" / "diagnostics"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"diagnostico_{execution_id}.zip"

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        added = 0
        for path in sorted(run_dir.iterdir()):
            if not path.is_file():
                continue
            if path.name in DIAGNOSTIC_FILES or path.name.startswith("evidence_"):
                zf.write(path, arcname=path.name)
                added += 1
        if not added:
            zf.writestr("README.txt", "Nenhum artefato técnico disponível para esta execução.\n")
    return output
