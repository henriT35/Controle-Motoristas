from datetime import date, timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps.core.models import SystemSettings
from .diagnostics import queue_pause_state
from .services import queue_import
from .scheduler_service import run_due_routines


def _paused() -> bool:
    return bool(queue_pause_state(Path(settings.BASE_DIR)).get("paused"))


@shared_task
def smart_scheduler():
    """Scheduler único da v0.8.2.0.

    Na VPS o Celery Beat chama este task a cada minuto. No Windows/local, o
    management command run_ssw_scheduler chama a MESMA regra sem Redis.
    """
    return run_due_routines()


@shared_task
def fast_sync():
    if _paused():
        return None
    today = timezone.localdate()
    cfg = SystemSettings.load()
    return queue_import(today - timedelta(days=max(cfg.recent_window_days - 1, 0)), today, kind="FAST")


@shared_task
def monthly_reconcile():
    if _paused():
        return None
    today = timezone.localdate()
    return queue_import(date(today.year, today.month, 1), today, kind="MONTH")


@shared_task
def run_robot_import(run_id):
    """Celery usa o mesmo watchdog do modo local; sem autoretry cego do lote."""
    call_command("run_ssw_robot_guarded", int(run_id))
    return int(run_id)
