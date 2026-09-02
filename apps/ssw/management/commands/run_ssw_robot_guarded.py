from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ssw.diagnostics import (
    DiagnosticRecorder,
    RunContext,
    first_attr,
    mark_run_error,
    mark_run_queued,
    pause_queue,
    queue_pause_state,
    read_robot_stage,
    safe_json_load,
    write_worker_state,
)
from apps.ssw.models import ImportRun
from apps.ssw.progress import read_import_progress
from apps.ssw.robot_bridge import execution_dir_for, execution_id_for, upsert_step

NON_RETRYABLE_CODES = {"INVALID_JOB"}


class Command(BaseCommand):
    help = "Executa run_ssw_robot em processo isolado com watchdog, heartbeat e diagnóstico."

    def add_arguments(self, parser):
        parser.add_argument("run_id", type=int)
        parser.add_argument("--force-while-paused", action="store_true")
        parser.add_argument("--hard-timeout", type=int, default=None, help="Timeout do domínio ROBÔ (compatibilidade).")
        parser.add_argument("--import-timeout", type=int, default=None, help="Timeout separado do Import Engine após DOWNLOADED.")
        parser.add_argument("--heartbeat", type=int, default=None)

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        run = self._get_run(options["run_id"])
        run_id = str(run.pk)
        execution_id = execution_id_for(run)
        run_dir = execution_dir_for(run)
        app_version = self._version(base_dir)

        rec = DiagnosticRecorder(
            run_dir,
            RunContext(
                execution_id=execution_id,
                run_pk=run_id,
                batch_id=str(first_attr(run, ("batch_id", "group_id", "queue_batch_id"), "") or "") or None,
                attempt=int(first_attr(run, ("attempt", "attempt_number", "retry_count"), 1) or 1),
                start_date=str(run.start_date),
                end_date=str(run.end_date),
                app_version=app_version,
            ),
        )

        paused = queue_pause_state(base_dir)
        if paused.get("paused") and not options["force_while_paused"]:
            # Proteção para corrida: o dispatch normal já não chama o worker quando pausado.
            # Se a pausa entrou entre o spawn e este handle, devolvemos o job para QUEUED.
            if run.status == ImportRun.Status.DISPATCHED:
                mark_run_queued(run, message="Fila SSW pausada; execução preservada para retomada.")
            rec.event(
                "BATCH_PAUSED_JOB_NOT_STARTED",
                level="WARNING",
                stage="QUEUED",
                message="Fila SSW está pausada; job preservado sem execução.",
                pause_state=paused,
            )
            write_worker_state(
                run_dir,
                status="NOT_STARTED_QUEUE_PAUSED",
                stage="QUEUED",
                watchdog_pid=os.getpid(),
                last_heartbeat_at=rec.last_progress_at,
            )
            self.stdout.write(self.style.WARNING("Fila SSW pausada. Job preservado em QUEUED."))
            return

        robot_timeout = options["hard_timeout"]
        if robot_timeout is None:
            robot_timeout = int(os.getenv("SSW_ROBOT_HARD_TIMEOUT_SECONDS", getattr(settings, "SSW_ROBOT_TIMEOUT_SECONDS", 900)))
        import_timeout = options["import_timeout"]
        if import_timeout is None:
            import_timeout = int(os.getenv("SSW_IMPORT_TIMEOUT_SECONDS", getattr(settings, "SSW_IMPORT_TIMEOUT_SECONDS", 3600)))
        heartbeat = options["heartbeat"]
        if heartbeat is None:
            heartbeat = int(os.getenv("SSW_ROBOT_HEARTBEAT_SECONDS", getattr(settings, "SSW_ROBOT_HEARTBEAT_SECONDS", 10)))
        robot_timeout = max(60, int(robot_timeout))
        import_timeout = max(300, int(import_timeout))
        heartbeat = max(2, int(heartbeat))

        manage_py = base_dir / "manage.py"
        if not manage_py.exists():
            raise CommandError(f"manage.py não encontrado em {base_dir}")

        cmd = [sys.executable, str(manage_py), "run_ssw_robot", run_id]
        popen_kwargs: dict[str, object] = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True

        child_log = run_dir / "worker_process.log"
        child_log.parent.mkdir(parents=True, exist_ok=True)
        rec.event(
            "WORKER_PROCESS_STARTING",
            stage="ROBOT_STARTING",
            message="Iniciando executor SSW homologado em processo isolado.",
            command=[sys.executable, "manage.py", "run_ssw_robot", run_id],
            robot_timeout_seconds=robot_timeout,
            import_timeout_seconds=import_timeout,
            heartbeat_seconds=heartbeat,
        )

        started = time.monotonic()
        started_epoch = time.time()
        last_beat = 0.0
        last_stage: str | None = None
        timeout_domain = "ROBOT"
        domain_started = started
        import_started_at: str | None = None
        timed_out = False
        timeout_code: str | None = None
        timeout_limit = robot_timeout
        exit_code: int | None = None

        with child_log.open("a", encoding="utf-8", errors="replace") as out:
            process = subprocess.Popen(
                cmd,
                cwd=str(base_dir),
                stdout=out,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                **popen_kwargs,
            )
            rec.event(
                "WORKER_PROCESS_STARTED",
                stage="ROBOT_STARTING",
                message="Executor SSW iniciado.",
                worker_pid=process.pid,
                watchdog_pid=os.getpid(),
            )
            write_worker_state(
                run_dir,
                status="RUNNING",
                stage="ROBOT_STARTING",
                watchdog_pid=os.getpid(),
                child_pid=process.pid,
                started_at=rec.last_progress_at,
                last_heartbeat_at=rec.last_progress_at,
                hard_timeout_seconds=robot_timeout,
                robot_timeout_seconds=robot_timeout,
                import_timeout_seconds=import_timeout,
                timeout_domain="ROBOT",
                heartbeat_seconds=heartbeat,
            )

            while True:
                exit_code = process.poll()
                now = time.monotonic()
                elapsed = now - started
                robot_stage, robot_status = read_robot_stage(run_dir)
                import_progress = read_import_progress(int(run_id)) or {}
                progress_epoch = float(import_progress.get("updated_at_epoch") or 0.0)
                progress_is_current = progress_epoch >= (started_epoch - 1.0)
                import_phase = str(import_progress.get("phase") or "").strip() if progress_is_current else ""

                downloaded = str(robot_stage or "").upper() == "DOWNLOADED"
                if (downloaded or import_phase) and timeout_domain != "IMPORT":
                    timeout_domain = "IMPORT"
                    domain_started = now
                    timeout_limit = import_timeout
                    import_started_at = self._now()
                    rec.event(
                        "WATCHDOG_DOMAIN_SWITCH",
                        stage="IMPORT_STARTING",
                        message="Download confirmado; watchdog passou a vigiar o Import Engine com timeout independente.",
                        worker_pid=process.pid,
                        robot_timeout_seconds=robot_timeout,
                        import_timeout_seconds=import_timeout,
                    )

                if timeout_domain == "IMPORT":
                    stage = f"IMPORT · {import_phase}" if import_phase else "IMPORT_STARTING"
                else:
                    stage = robot_stage or "ROBOT_RUNNING"

                if stage and stage != last_stage:
                    event_name = "IMPORT_PROGRESS" if timeout_domain == "IMPORT" else "WORKER_PROGRESS"
                    fields = {
                        "worker_pid": process.pid,
                        "robot_status": robot_status,
                        "timeout_domain": timeout_domain,
                    }
                    if timeout_domain == "IMPORT" and progress_is_current:
                        fields.update(
                            import_phase=import_phase,
                            import_percent=import_progress.get("percent"),
                            import_current=import_progress.get("current"),
                            import_total=import_progress.get("total"),
                            import_message=import_progress.get("message"),
                        )
                    rec.event(
                        event_name,
                        stage=stage,
                        message=(
                            f"Import Engine: {import_progress.get('message') or import_phase}"
                            if timeout_domain == "IMPORT" and progress_is_current
                            else f"Etapa observada: {stage}"
                        ),
                        **fields,
                    )
                    last_stage = stage
                    state_fields = dict(
                        status="RUNNING",
                        stage=stage,
                        watchdog_pid=os.getpid(),
                        child_pid=process.pid,
                        last_heartbeat_at=rec.last_progress_at,
                        timeout_domain=timeout_domain,
                        robot_timeout_seconds=robot_timeout,
                        import_timeout_seconds=import_timeout,
                    )
                    if import_started_at:
                        state_fields["import_started_at"] = import_started_at
                    if timeout_domain == "IMPORT" and progress_is_current:
                        state_fields.update(
                            import_phase=import_phase,
                            import_percent=import_progress.get("percent"),
                            import_current=import_progress.get("current"),
                            import_total=import_progress.get("total"),
                            import_message=import_progress.get("message"),
                        )
                    write_worker_state(run_dir, **state_fields)

                if exit_code is not None:
                    break

                domain_elapsed = now - domain_started
                if now - last_beat >= heartbeat:
                    rec.event(
                        "WORKER_HEARTBEAT",
                        stage=stage or last_stage or "RUNNING",
                        message="Worker ativo.",
                        progress=False,
                        worker_pid=process.pid,
                        watchdog_pid=os.getpid(),
                        process_alive=True,
                        timeout_domain=timeout_domain,
                        domain_elapsed_ms=int(domain_elapsed * 1000),
                        domain_timeout_seconds=timeout_limit,
                        total_elapsed_ms=int(elapsed * 1000),
                        import_percent=import_progress.get("percent") if progress_is_current else None,
                    )
                    write_worker_state(
                        run_dir,
                        status="RUNNING",
                        stage=stage or last_stage or "RUNNING",
                        watchdog_pid=os.getpid(),
                        child_pid=process.pid,
                        last_heartbeat_at=self._now(),
                        timeout_domain=timeout_domain,
                        domain_elapsed_ms=int(domain_elapsed * 1000),
                        domain_timeout_seconds=timeout_limit,
                        import_started_at=import_started_at,
                        import_phase=import_phase or None,
                        import_percent=import_progress.get("percent") if progress_is_current else None,
                    )
                    last_beat = now

                if domain_elapsed >= timeout_limit:
                    timed_out = True
                    timeout_code = "IMPORT_HARD_TIMEOUT" if timeout_domain == "IMPORT" else "ROBOT_HARD_TIMEOUT"
                    timeout_subject = "Import Engine" if timeout_domain == "IMPORT" else "Robô SSW"
                    rec.event(
                        "WATCHDOG_TIMEOUT",
                        level="ERROR",
                        stage=stage or last_stage or "RUNNING",
                        message=f"{timeout_subject} excedeu o limite externo do seu domínio e será encerrado.",
                        worker_pid=process.pid,
                        timeout_domain=timeout_domain,
                        domain_timeout_seconds=timeout_limit,
                        domain_elapsed_ms=int(domain_elapsed * 1000),
                        total_elapsed_ms=int(elapsed * 1000),
                        error_code=timeout_code,
                    )
                    write_worker_state(
                        run_dir,
                        status="TIMEOUT_TERMINATING",
                        stage=stage or last_stage or "RUNNING",
                        watchdog_pid=os.getpid(),
                        child_pid=process.pid,
                        last_heartbeat_at=self._now(),
                        timeout_domain=timeout_domain,
                        error_code=timeout_code,
                    )
                    self._terminate_tree(process, rec, stage or last_stage)
                    exit_code = process.poll()
                    break

                time.sleep(min(1.0, heartbeat / 2))

        total_ms = int((time.monotonic() - started) * 1000)
        try:
            run.refresh_from_db()
        except Exception:
            pass

        if timed_out:
            code = timeout_code or ("IMPORT_HARD_TIMEOUT" if timeout_domain == "IMPORT" else "ROBOT_HARD_TIMEOUT")
            subject = "Import Engine" if code == "IMPORT_HARD_TIMEOUT" else "Robô SSW"
            limit = import_timeout if code == "IMPORT_HARD_TIMEOUT" else robot_timeout
            message = f"{subject} excedeu {limit}s na etapa {last_stage or 'desconhecida'}."
            self._finalize_error(
                run,
                rec,
                run_dir,
                execution_id=execution_id,
                error_code=code,
                message=message,
                stage=last_stage,
                total_ms=total_ms,
                worker_pid=process.pid,
                killed=True,
                queue_paused=True,
                failed_component="import_engine" if code == "IMPORT_HARD_TIMEOUT" else "robot_worker",
            )
            raise CommandError(message)

        # Ler o erro real ANTES de reduzir tudo a WORKER_EXIT_NONZERO.
        result_json = safe_json_load(run_dir / "result.json")
        final_stage, final_status = read_robot_stage(run_dir)
        try:
            run.refresh_from_db()
        except Exception:
            pass
        error_code, error_message = self._reported_error(run, result_json, final_status)
        run_status = str(run.status or "").upper()
        effective_final_stage = (
            last_stage
            if str(last_stage or "").startswith("IMPORT")
            else (final_stage or last_stage)
        )

        if error_code or run_status == ImportRun.Status.ERROR:
            code = error_code or "ROBOT_REPORTED_ERROR"
            message = error_message or str(run.message or f"Robô finalizou em {run_status}.")
            # Qualquer erro de uma execução robotizada interrompe a cadeia mensal.
            # Os códigos externos explicam a causa; a pausa explícita evita fila
            # "parada sem motivo" quando a falha veio do importador após DOWNLOADED.
            should_pause = True
            self._finalize_error(
                run,
                rec,
                run_dir,
                execution_id=execution_id,
                error_code=code,
                message=message,
                stage=effective_final_stage,
                total_ms=total_ms,
                worker_pid=process.pid,
                killed=False,
                queue_paused=should_pause,
                exit_code=exit_code,
                result_json=result_json,
                failed_component=(
                    "import_engine"
                    if code.startswith("IMPORT_") or str(effective_final_stage or "").startswith("IMPORT")
                    else "robot_worker"
                ),
            )
            raise CommandError(f"{code}: {message}")

        if exit_code != 0:
            code = "WORKER_EXIT_NONZERO"
            message = f"Worker SSW encerrou com código {exit_code} sem erro estruturado."
            self._finalize_error(
                run,
                rec,
                run_dir,
                execution_id=execution_id,
                error_code=code,
                message=message,
                stage=effective_final_stage,
                total_ms=total_ms,
                worker_pid=process.pid,
                killed=False,
                queue_paused=True,
                exit_code=exit_code,
                result_json=result_json,
                failed_component=(
                    "import_engine" if str(effective_final_stage or "").startswith("IMPORT") else "robot_worker"
                ),
            )
            raise CommandError(message)

        # O comando filho só é considerado sucesso quando o ImportRun saiu de estado ativo.
        if run_status not in {ImportRun.Status.SUCCESS, ImportRun.Status.WARNING}:
            code = "WORKER_PROCESS_LOST"
            message = f"Worker terminou com código 0, mas ImportRun permaneceu em {run_status or 'estado desconhecido'}."
            self._finalize_error(
                run,
                rec,
                run_dir,
                execution_id=execution_id,
                error_code=code,
                message=message,
                stage=effective_final_stage,
                total_ms=total_ms,
                worker_pid=process.pid,
                killed=False,
                queue_paused=True,
                exit_code=exit_code,
                result_json=result_json,
                failed_component=(
                    "import_engine" if str(effective_final_stage or "").startswith("IMPORT") else "robot_worker"
                ),
            )
            raise CommandError(message)

        rec.event(
            "WORKER_EXITED",
            stage=effective_final_stage or run_status,
            message="Worker SSW finalizou normalmente e o Painel confirmou o resultado.",
            worker_pid=process.pid,
            exit_code=exit_code,
            total_elapsed_ms=total_ms,
            import_run_status=run_status,
            robot_status=final_status,
        )
        write_worker_state(
            run_dir,
            status="COMPLETED",
            stage=effective_final_stage or run_status,
            watchdog_pid=os.getpid(),
            child_pid=process.pid,
            exit_code=exit_code,
            last_heartbeat_at=self._now(),
            completed_at=self._now(),
        )
        rec.diagnostic(
            result="COMPLETED",
            error_code=None,
            failed_component=None,
            failed_stage=None,
            last_successful_stage=effective_final_stage,
            total_elapsed_ms=total_ms,
            worker_pid=process.pid,
            worker_was_killed=False,
            queue_paused=False,
            import_run_status=run_status,
            retryable=False,
        )
        self.stdout.write(self.style.SUCCESS(f"Execução {execution_id} concluída pelo watchdog."))

    @staticmethod
    def _get_run(run_id: int) -> ImportRun:
        try:
            return ImportRun.objects.get(pk=run_id)
        except ImportRun.DoesNotExist as exc:
            raise CommandError(f"ImportRun não encontrado: {run_id}") from exc

    @staticmethod
    def _version(base_dir: Path) -> str:
        try:
            return (base_dir / "VERSION.txt").read_text(encoding="utf-8").strip()
        except Exception:
            return "unknown"

    @staticmethod
    def _now() -> str:
        from apps.ssw.diagnostics import iso_now

        return iso_now()

    @staticmethod
    def _reported_error(run, result_json: dict, final_status: dict) -> tuple[str | None, str | None]:
        code = result_json.get("error_code") or final_status.get("error_code")
        message = result_json.get("error_message") or final_status.get("error_message")
        db_message = str(getattr(run, "message", "") or "")
        if not code and ":" in db_message:
            prefix, rest = db_message.split(":", 1)
            normalized = prefix.strip().upper()
            if normalized.replace("_", "").isalnum() and len(normalized) <= 64:
                code = normalized
                message = message or rest.strip()
        return (str(code) if code else None, str(message) if message else None)

    def _finalize_error(
        self,
        run,
        rec: DiagnosticRecorder,
        run_dir: Path,
        *,
        execution_id: str,
        error_code: str,
        message: str,
        stage: str | None,
        total_ms: int,
        worker_pid: int,
        killed: bool,
        queue_paused: bool,
        exit_code: int | None = None,
        result_json: dict | None = None,
        failed_component: str = "robot_worker",
    ) -> None:
        mark_run_error(run, error_code=error_code, message=message)
        try:
            upsert_step(run, "Watchdog", "ERROR", f"{error_code}: {message}")
        except Exception:
            pass
        if queue_paused:
            pause_queue(
                Path(settings.BASE_DIR),
                reason=message,
                execution_id=execution_id,
                error_code=error_code,
            )
            rec.event(
                "BATCH_PAUSED",
                level="ERROR",
                stage=stage or "ERROR",
                message="Fila SSW pausada para evitar falhas em cascata/reprocessamento do lote.",
                error_code=error_code,
            )
        rec.event(
            "ROBOT_EXECUTION_FAILED",
            level="ERROR",
            stage=stage or "ERROR",
            message=message,
            worker_pid=worker_pid,
            exit_code=exit_code,
            error_code=error_code,
            result_json=result_json or {},
        )
        write_worker_state(
            run_dir,
            status="ERROR",
            stage=stage or "ERROR",
            watchdog_pid=os.getpid(),
            child_pid=worker_pid,
            exit_code=exit_code,
            error_code=error_code,
            error_message=message,
            last_heartbeat_at=self._now(),
            completed_at=self._now(),
        )
        rec.diagnostic(
            result="ERROR",
            error_code=error_code,
            failed_component=failed_component,
            failed_stage=stage,
            total_elapsed_ms=total_ms,
            worker_pid=worker_pid,
            worker_was_killed=killed,
            queue_paused=queue_paused,
            completed_windows_preserved=True,
            retryable=error_code not in NON_RETRYABLE_CODES,
            probable_cause=message,
            recommended_action=(
                "Verificar o diagnóstico, confirmar o SSW disponível, retomar a fila e reprocessar somente esta janela."
                if queue_paused
                else "Corrigir esta janela e reprocessá-la sem recriar o lote inteiro."
            ),
        )

    @staticmethod
    def _terminate_tree(process, rec: DiagnosticRecorder, stage: str | None) -> None:
        rec.event(
            "WATCHDOG_TERMINATE_SENT",
            level="ERROR",
            stage=stage,
            message="Solicitando encerramento da árvore do worker/browser.",
            worker_pid=process.pid,
        )
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    check=False,
                )
            else:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except Exception:
                    process.terminate()
            try:
                process.wait(timeout=10)
                return
            except subprocess.TimeoutExpired:
                pass
        except Exception as exc:
            rec.event(
                "WATCHDOG_TERMINATE_FAILED",
                level="CRITICAL",
                stage=stage,
                message=f"Falha ao terminar worker: {exc}",
                worker_pid=process.pid,
            )

        rec.event(
            "WATCHDOG_KILL_SENT",
            level="CRITICAL",
            stage=stage,
            message="Forçando encerramento do worker/browser.",
            worker_pid=process.pid,
        )
        try:
            if os.name != "nt":
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:
                    process.kill()
            else:
                process.kill()
            process.wait(timeout=5)
        except Exception:
            pass
