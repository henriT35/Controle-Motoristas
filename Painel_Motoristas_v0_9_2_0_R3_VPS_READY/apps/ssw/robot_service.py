from __future__ import annotations

import logging
from queue import Queue
from threading import Thread
from typing import Any

from django.db import close_old_connections
from django.utils import timezone

from .dispatch import dispatch_next_robot_run
from .importer import import_ssw_delivery_file
from .models import ImportRun
from .progress import clear_import_progress, publish_import_progress
from .robot_bridge import (
    RobotBridgeError,
    execution_id_for,
    run_homologated_robot,
    upsert_step,
)

logger = logging.getLogger("painel.ssw.robot")

SERVICE_BUILD = "0.3.0.9-watchdog-import-domain"

EVENT_TO_STEP = {
    "ROBOT_STARTING": "Robô iniciando",
    "AUTHENTICATING": "Autenticação SSW",
    "REQUESTING_REPORT": "Solicitação relatório",
    "WAITING_DOWNLOAD": "Download",
    "DOWNLOADED": "Download",
    "ERROR": "Robô SSW",
}

_STOP = object()


def _persist_robot_event(run_id: int, event: Any) -> None:
    """Persiste um evento fora do contexto interno do Playwright.

    O Playwright Sync usa um loop asyncio/greenlet internamente. Fazer ORM do
    Django diretamente no status_callback dispara SynchronousOnlyOperation.
    Esta função roda numa thread dedicada e usa uma conexão Django própria.
    """
    close_old_connections()
    try:
        run = ImportRun.objects.get(pk=run_id)
        state = str(getattr(event, "state", "") or "").upper()
        detail = str(getattr(event, "detail", "") or "")
        step_name = EVENT_TO_STEP.get(state, "Robô SSW")
        step_status = "SUCCESS" if state == "DOWNLOADED" else ("ERROR" if state == "ERROR" else "RUNNING")

        upsert_step(run, step_name, step_status, detail or state)

        update_fields: list[str] = ["status", "message"]
        run.message = (detail or state)[:4000]
        if state == "ERROR":
            run.status = ImportRun.Status.ERROR
            run.error_count = max(run.error_count, 1)
            update_fields.append("error_count")
        else:
            run.status = ImportRun.Status.RUNNING
        run.save(update_fields=update_fields)
    finally:
        close_old_connections()


class RobotEventPump:
    """Fila thread-safe entre o callback do Playwright e o ORM do Django."""

    def __init__(self, run_id: int):
        self.run_id = run_id
        self.queue: Queue[Any] = Queue()
        self.error: Exception | None = None
        self.thread = Thread(
            target=self._consume,
            name=f"ssw-status-{run_id}",
            daemon=True,
        )

    def start(self) -> "RobotEventPump":
        self.thread.start()
        return self

    def callback(self, event: Any) -> None:
        # IMPORTANTE: nenhuma chamada ao ORM aqui.
        self.queue.put(event)

    def _consume(self) -> None:
        while True:
            item = self.queue.get()
            try:
                if item is _STOP:
                    return
                try:
                    _persist_robot_event(self.run_id, item)
                except Exception as exc:  # progresso não deve derrubar o Playwright
                    self.error = self.error or exc
                    logger.exception(
                        "Falha ao persistir evento do robô em thread separada run=%s",
                        self.run_id,
                    )
            finally:
                self.queue.task_done()

    def stop(self) -> None:
        # Garante que todos os eventos anteriores sejam persistidos primeiro.
        self.queue.put(_STOP)
        self.queue.join()
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            logger.error("Thread de progresso do robô não encerrou no prazo run=%s", self.run_id)


def execute_robot_import(run_id: int) -> int:
    run = ImportRun.objects.select_related("requested_by").get(pk=run_id)
    allowed = {ImportRun.Status.QUEUED, ImportRun.Status.DISPATCHED, ImportRun.Status.ERROR}
    if run.status not in allowed:
        return run.pk

    # Evita que o watchdog confunda um snapshot de tentativa anterior com a
    # importação atual do mesmo run. Observabilidade é sempre best-effort.
    clear_import_progress(run.pk)

    run.status = ImportRun.Status.RUNNING
    run.started_at = run.started_at or timezone.now()
    run.finished_at = None
    run.message = f"Robô SSW homologado iniciado ({execution_id_for(run)})."
    run.save(update_fields=["status", "started_at", "finished_at", "message"])

    upsert_step(run, "Robô iniciando", "RUNNING", "Chamando API robot_ssw.run_job().")
    should_dispatch_next = False
    download_completed = False
    pump = RobotEventPump(run.pk).start()

    try:
        # O callback só enfileira eventos. O ORM roda na thread RobotEventPump.
        artifact = run_homologated_robot(run, status_callback=pump.callback)
        download_completed = True

        # Espera os eventos do robô (inclusive DOWNLOADED) chegarem ao banco.
        pump.stop()
        run.refresh_from_db()

        if pump.error:
            logger.warning(
                "Robô concluiu, mas houve falha em alguma atualização de progresso run=%s: %s",
                run.pk,
                pump.error,
            )

        # DOWNLOADED é só a fronteira Robô -> Painel. Não marcar SUCCESS aqui.
        upsert_step(
            run,
            "Download",
            "SUCCESS",
            f"DOWNLOADED: {artifact.path.name} ({artifact.size} bytes; sha256 {artifact.sha256[:16]}…).",
        )
        upsert_step(run, "Validação", "RUNNING", "Painel assumiu a execução e está validando o arquivo recebido.")
        publish_import_progress(
            run.pk,
            phase="Validação",
            message="Download concluído; Import Engine assumiu a execução.",
            percent=1,
            current=0,
            total=None,
        )

        imported_run, _stats = import_ssw_delivery_file(
            artifact.path,
            kind=run.kind,
            requested_by=run.requested_by,
            existing_run=run,
            source_label="Robô SSW homologado",
        )
        should_dispatch_next = imported_run.status in {ImportRun.Status.SUCCESS, ImportRun.Status.WARNING}
        return imported_run.pk

    except RobotBridgeError as exc:
        # Flush dos eventos já emitidos antes de registrar o erro final.
        pump.stop()
        run.refresh_from_db()
        logger.exception("Falha do robô homologado run=%s code=%s", run.pk, exc.code)
        upsert_step(run, "Robô SSW", "ERROR", f"{exc.code}: {exc}")
        run.status = ImportRun.Status.ERROR
        run.error_count = max(run.error_count, 1)
        run.finished_at = timezone.now()
        run.message = f"{exc.code}: {exc}"[:4000]
        run.save(update_fields=["status", "error_count", "finished_at", "message"])
        raise

    except Exception as exc:
        pump.stop()
        run.refresh_from_db()
        error_code = "IMPORT_ENGINE_ERROR" if download_completed else "ROBOT_UNEXPECTED"
        logger.exception("Falha inesperada na integração SSW run=%s code=%s", run.pk, error_code)
        structured = f"{error_code}: {exc}"
        upsert_step(run, "Erro", "ERROR", structured)
        if download_completed:
            publish_import_progress(
                run.pk, phase="Erro", message=structured, percent=100, status="ERROR"
            )
        run.status = ImportRun.Status.ERROR
        run.error_count = max(run.error_count, 1)
        run.finished_at = timezone.now()
        run.message = structured[:4000]
        run.save(update_fields=["status", "error_count", "finished_at", "message"])
        raise

    finally:
        # stop() é idempotente o suficiente para o caminho normal/erro? Evita
        # chamar novamente se a thread já encerrou.
        if pump.thread.is_alive():
            try:
                pump.stop()
            except Exception:
                logger.exception("Falha ao encerrar thread de progresso run=%s", run.pk)

        # Histórico mensal é sequencial e só avança após aplicação bem-sucedida/aviso.
        if should_dispatch_next:
            try:
                dispatch_next_robot_run()
            except Exception:
                logger.exception("Não foi possível despachar o próximo ImportRun após run=%s", run.pk)
