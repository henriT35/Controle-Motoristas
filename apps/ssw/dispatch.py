from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .diagnostics import pause_queue, queue_pause_state, reconcile_orphan_runs
from .models import ImportRun, ImportStep
from .robot_bridge import check_robot_ready, execution_id_for

logger = logging.getLogger("painel.ssw.dispatch")


def _queue_is_paused() -> bool:
    return bool(queue_pause_state(Path(settings.BASE_DIR)).get("paused"))


def _spawn_run(run_id: int) -> bool:
    if not getattr(settings, "SSW_ROBOT_ENABLED", False):
        logger.info("Robô SSW desabilitado; run=%s permanece na fila", run_id)
        return False

    if _queue_is_paused():
        logger.warning("Fila SSW pausada; run=%s não será iniciado", run_id)
        return False

    mode = getattr(settings, "SSW_ROBOT_DISPATCH_MODE", "local_process").strip().lower()
    if mode == "celery":
        from .tasks import run_robot_import

        run_robot_import.delay(run_id)
        return True
    if mode != "local_process":
        raise RuntimeError(f"SSW_ROBOT_DISPATCH_MODE inválido: {mode}")

    # Preflight rápido: NÃO abre Chromium aqui. O browser precisa nascer dentro do
    # processo protegido pelo watchdog, para um launch travado não congelar a view Django.
    ready, detail = check_robot_ready(launch_browser=False)
    if not ready:
        raise RuntimeError("Robô SSW homologado não está pronto. " + detail)

    log_dir = settings.BASE_DIR / "local_data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "robot-worker.log"
    cmd = [
        sys.executable,
        str(settings.BASE_DIR / "manage.py"),
        "run_ssw_robot_guarded",
        str(run_id),
    ]

    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True

    with log_path.open("a", encoding="utf-8") as log:
        subprocess.Popen(
            cmd,
            cwd=str(settings.BASE_DIR),
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            close_fds=(os.name != "nt"),
            **kwargs,
        )
    logger.info("Robô SSW protegido por watchdog despachado run=%s", run_id)
    return True


def dispatch_next_robot_run() -> bool:
    if not getattr(settings, "SSW_ROBOT_ENABLED", False):
        return False

    # Recupera jobs zumbis de processo/reboot anterior antes de decidir que existe
    # execução ativa. Se recuperar, a própria rotina pausa a fila para inspeção.
    try:
        recovered = reconcile_orphan_runs(Path(settings.BASE_DIR))
        if recovered:
            logger.error("Execuções órfãs reconciliadas: %s", recovered)
    except Exception:
        logger.exception("Falha ao reconciliar execuções órfãs do robô SSW")

    if _queue_is_paused():
        logger.warning("Fila SSW pausada; nenhum próximo job será despachado")
        return False

    if ImportRun.objects.filter(
        status__in=[ImportRun.Status.DISPATCHED, ImportRun.Status.RUNNING]
    ).exists():
        return False

    queued = (
        ImportRun.objects.filter(status=ImportRun.Status.QUEUED)
        .order_by("created_at", "pk")
        .first()
    )
    if not queued:
        return False

    queued.status = ImportRun.Status.DISPATCHED
    queued.message = "Execução entregue ao watchdog do robô SSW; aguardando aceite do executor."
    queued.save(update_fields=["status", "message"])
    ImportStep.objects.create(
        run=queued,
        name="Despacho",
        status="RUNNING",
        occurred_at=timezone.now(),
        message="Processo watchdog solicitado; aguardando o executor assumir a tarefa.",
    )
    try:
        spawned = _spawn_run(queued.pk)
        if spawned:
            step = queued.steps.filter(name="Despacho", status="RUNNING").order_by("-id").first()
            if step:
                step.status = "SUCCESS"
                step.message = "Watchdog despachado; aguardando heartbeat do executor."
                step.save(update_fields=["status", "message"])
        return spawned
    except Exception as exc:
        queued.status = ImportRun.Status.ERROR
        queued.error_count = max(queued.error_count, 1)
        queued.finished_at = timezone.now()
        queued.message = f"ROBOT_PREFLIGHT_FAILED: {exc}"[:4000]
        queued.save(update_fields=["status", "error_count", "finished_at", "message"])
        ImportStep.objects.create(
            run=queued,
            name="Preflight/Despacho",
            status="ERROR",
            occurred_at=timezone.now(),
            message=queued.message,
        )
        pause_queue(
            Path(settings.BASE_DIR),
            reason=queued.message,
            execution_id=execution_id_for(queued),
            error_code="ROBOT_PREFLIGHT_FAILED",
        )
        logger.exception("Falha ao despachar robô SSW run=%s; fila pausada", queued.pk)
        return False


def dispatch_robot_run(run_id: int, *, priority: bool = False) -> bool:
    run = ImportRun.objects.get(pk=run_id)
    if run.status not in {ImportRun.Status.QUEUED, ImportRun.Status.DISPATCHED}:
        return False
    if _queue_is_paused():
        if run.status == ImportRun.Status.DISPATCHED:
            run.status = ImportRun.Status.QUEUED
            run.message = "Fila SSW pausada; aguardando retomada."
            run.save(update_fields=["status", "message"])
        return False
    if run.status == ImportRun.Status.DISPATCHED:
        return True

    if priority:
        if ImportRun.objects.filter(
            status__in=[ImportRun.Status.DISPATCHED, ImportRun.Status.RUNNING]
        ).exists():
            return False
        run.status = ImportRun.Status.DISPATCHED
        run.message = "Retry prioritário entregue ao watchdog do robô SSW; aguardando aceite do executor."
        run.save(update_fields=["status", "message"])
        ImportStep.objects.create(
            run=run,
            name="Despacho",
            status="RUNNING",
            occurred_at=timezone.now(),
            message="Retry: processo watchdog solicitado; aguardando o executor assumir a tarefa.",
        )
        try:
            spawned = _spawn_run(run.pk)
            if spawned:
                step = run.steps.filter(name="Despacho", status="RUNNING").order_by("-id").first()
                if step:
                    step.status = "SUCCESS"
                    step.message = "Watchdog despachado; aguardando heartbeat do executor."
                    step.save(update_fields=["status", "message"])
            return spawned
        except Exception as exc:
            run.status = ImportRun.Status.ERROR
            run.error_count = max(run.error_count, 1)
            run.finished_at = timezone.now()
            run.message = f"ROBOT_PREFLIGHT_FAILED: {exc}"[:4000]
            run.save(update_fields=["status", "error_count", "finished_at", "message"])
            pause_queue(
                Path(settings.BASE_DIR),
                reason=run.message,
                execution_id=execution_id_for(run),
                error_code="ROBOT_PREFLIGHT_FAILED",
            )
            logger.exception("Falha no retry prioritário run=%s", run.pk)
            return False

    return dispatch_next_robot_run()
