from datetime import date, timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps.core.models import SystemSettings
from .diagnostics import queue_pause_state
from .models import ImportRun
from .services import queue_import
from .schedule_config import load_schedule_config


def _paused() -> bool:
    return bool(queue_pause_state(Path(settings.BASE_DIR)).get("paused"))


@shared_task
def smart_scheduler():
    """Orquestrador frequente; a cadência real é configurada no Painel.

    O Celery Beat acorda a cada minuto, mas esta função só cria um FAST quando
    o intervalo configurado venceu. O mesmo lock/deduplicação de queue_import
    protege contra concorrência com o botão Atualizar agora.
    """
    if _paused():
        return []

    now = timezone.localtime()
    today = now.date()
    cfg = SystemSettings.load()
    runtime = load_schedule_config()
    queued = []

    last_fast = ImportRun.objects.filter(kind=ImportRun.Kind.FAST).order_by("-created_at").first()
    interval_seconds = int(runtime["interval_minutes"]) * 60
    fast_due = bool(runtime["enabled"]) and (
        not last_fast or (now - timezone.localtime(last_fast.created_at)).total_seconds() >= interval_seconds
    )
    if fast_due:
        queued.append(queue_import(today - timedelta(days=max(cfg.recent_window_days - 1, 0)), today, kind=ImportRun.Kind.FAST))

    reconcile_hour = cfg.monthly_reconcile_time.hour
    already_month = ImportRun.objects.filter(kind=ImportRun.Kind.MONTH, created_at__date=today).exists()
    if runtime["enabled"] and now.hour == reconcile_hour and not already_month:
        queued.append(queue_import(date(today.year, today.month, 1), today, kind=ImportRun.Kind.MONTH))
    return queued


@shared_task
def fast_sync():
    if _paused():
        return None
    today = timezone.localdate()
    cfg = SystemSettings.load()
    return queue_import(today - timedelta(days=max(cfg.recent_window_days - 1, 0)), today, kind=ImportRun.Kind.FAST)


@shared_task
def monthly_reconcile():
    if _paused():
        return None
    today = timezone.localdate()
    return queue_import(date(today.year, today.month, 1), today, kind=ImportRun.Kind.MONTH)


@shared_task
def run_robot_import(run_id):
    """Celery usa o mesmo watchdog do modo local; sem autoretry cego do lote."""
    call_command("run_ssw_robot_guarded", int(run_id))
    return int(run_id)
