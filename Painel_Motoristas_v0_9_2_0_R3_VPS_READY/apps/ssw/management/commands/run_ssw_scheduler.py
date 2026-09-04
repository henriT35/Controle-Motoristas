from __future__ import annotations

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.warmup import warm_navigation_cache

from apps.drivers.evaluation import (
    ensure_actions_activation_date, finalize_expired_pickup_opportunities, materialize_exact_pickup_opportunities,
    sync_quality_events_for_movements, sync_retention_obligations,
)

from apps.ssw.schedule_config import write_scheduler_state
from apps.ssw.scheduler_service import run_due_routines


class Command(BaseCommand):
    help = "Mantém o scheduler SSW ativo no modo Windows/local sem depender de Redis/Celery Beat."

    def add_arguments(self, parser):
        parser.add_argument("--poll-seconds", type=int, default=30)
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        poll = max(15, int(options["poll_seconds"] or 30))
        once = bool(options["once"])
        self.stdout.write(self.style.SUCCESS(f"Scheduler SSW ativo · verificação a cada {poll}s"))
        last_evaluation_day = None
        while True:
            try:
                today = timezone.localdate()
                if last_evaluation_day != today:
                    activation = ensure_actions_activation_date()
                    created = sync_quality_events_for_movements()
                    retention = sync_retention_obligations(end=today)
                    exact_history = materialize_exact_pickup_opportunities(start=activation, end=today)
                    finalized = finalize_expired_pickup_opportunities(as_of=today)
                    warmed = warm_navigation_cache(reference_date=today)
                    snapshots = warmed.get("snapshots_current", 0)
                    self.stdout.write(
                        f"avaliacao-v3: ativacao={activation} rom13={created} "
                        f"retencoes={retention} exatas={exact_history} finalizadas={finalized} snapshots={snapshots} cache={warmed}"
                    )
                    last_evaluation_day = today
                report = run_due_routines()
                self.stdout.write(
                    f"ciclo: disparadas={len(report.get('triggered', []))} ignoradas={len(report.get('skipped', []))}"
                )
            except KeyboardInterrupt:
                write_scheduler_state(message="Scheduler encerrado manualmente.")
                return
            except Exception as exc:
                write_scheduler_state(message=f"Erro no scheduler: {exc}", last_error=str(exc))
                self.stderr.write(self.style.ERROR(f"Scheduler SSW: {exc}"))
            if once:
                return
            time.sleep(poll)
