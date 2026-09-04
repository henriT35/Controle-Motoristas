from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .diagnostics import queue_pause_state
from .models import ImportRun
from .schedule_config import (
    get_routine,
    load_schedule_config,
    mark_routine_triggered,
    routine_is_in_active_window,
    routine_last_anchor,
    routine_period,
    write_scheduler_state,
)
from .services import queue_import, queue_period_chunks

ACTIVE_STATUSES = {
    ImportRun.Status.QUEUED,
    ImportRun.Status.DISPATCHED,
    ImportRun.Status.RUNNING,
}


def _paused() -> bool:
    return bool(queue_pause_state(Path(settings.BASE_DIR)).get("paused"))


def _last_cycle_finished_at(routine: dict):
    ids = [int(x) for x in (routine.get("last_run_ids") or []) if str(x).isdigit()]
    if not ids:
        return None, False
    runs = list(ImportRun.objects.filter(pk__in=ids).only("pk", "status", "finished_at"))
    if not runs:
        return None, False
    active = any(run.status in ACTIVE_STATUSES for run in runs)
    finished = [run.finished_at for run in runs if run.finished_at]
    latest_finished = max(finished) if finished else None
    return latest_finished, active


def routine_due(routine: dict, *, now=None) -> tuple[bool, str]:
    now = timezone.localtime(now or timezone.now())
    if not routine.get("enabled"):
        return False, "rotina desativada"
    if not routine_is_in_active_window(routine, now):
        return False, "fora da janela diária"
    if routine_period(routine, now.date()) is None:
        return False, "período ainda não disponível"

    last_finished, active = _last_cycle_finished_at(routine)
    if active:
        return False, "ciclo anterior ainda em execução"

    anchor = routine_last_anchor(routine)
    if last_finished and (not anchor or last_finished > anchor):
        anchor = last_finished
    if not anchor:
        return True, "primeira execução"

    interval = timedelta(minutes=int(routine.get("interval_minutes") or 120))
    if now >= timezone.localtime(anchor) + interval:
        return True, "intervalo vencido"
    return False, "aguardando próximo intervalo"


def trigger_routine(routine: dict, *, requested_by=None, now=None) -> list[int]:
    now = timezone.localtime(now or timezone.now())
    period = routine_period(routine, now.date())
    if not period:
        return []
    start, end = period
    if routine.get("range_mode") == "FIXED":
        ids = queue_period_chunks(start, end, kind=ImportRun.Kind.HISTORY, requested_by=requested_by)
    else:
        ids = [queue_import(start, end, kind=ImportRun.Kind.FAST, requested_by=requested_by)]
    mark_routine_triggered(routine["id"], ids, triggered_at=now)
    return ids


def run_due_routines(*, now=None) -> dict:
    now = timezone.localtime(now or timezone.now())
    config = load_schedule_config()
    report = {"triggered": [], "skipped": [], "error": None}

    if _paused():
        report["error"] = "Fila SSW pausada."
        write_scheduler_state(last_cycle=now.isoformat(), message=report["error"], report=report)
        return report
    if not config.get("enabled"):
        report["error"] = "Automação SSW desativada no Painel."
        write_scheduler_state(last_cycle=now.isoformat(), message=report["error"], report=report)
        return report

    for routine in config.get("routines", []):
        due, reason = routine_due(routine, now=now)
        if not due:
            report["skipped"].append({"id": routine["id"], "name": routine["name"], "reason": reason})
            continue
        try:
            ids = trigger_routine(routine, now=now)
            if ids:
                report["triggered"].append({"id": routine["id"], "name": routine["name"], "run_ids": ids})
            else:
                report["skipped"].append({"id": routine["id"], "name": routine["name"], "reason": "período vazio"})
        except Exception as exc:
            report["skipped"].append({"id": routine["id"], "name": routine["name"], "reason": f"erro: {exc}"})

    message = (
        f"{len(report['triggered'])} rotina(s) disparada(s)."
        if report["triggered"]
        else "Nenhuma rotina venceu neste ciclo."
    )
    write_scheduler_state(last_cycle=now.isoformat(), message=message, report=report)
    return report


def trigger_routine_by_id(routine_id: str, *, requested_by=None) -> list[int]:
    routine = get_routine(routine_id)
    if not routine:
        raise ValueError("Rotina SSW não encontrada.")
    if _paused():
        raise RuntimeError("A fila SSW está pausada.")
    return trigger_routine(routine, requested_by=requested_by)
