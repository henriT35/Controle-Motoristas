from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ssw.diagnostics import reconcile_orphan_runs


class Command(BaseCommand):
    help = "Reconcilia jobs SSW DISPATCHED/RUNNING sem processo/heartbeat vivo."

    def handle(self, *args, **options):
        recovered = reconcile_orphan_runs(Path(settings.BASE_DIR))
        if recovered:
            self.stdout.write(self.style.WARNING(f"Órfãos recuperados: {recovered}. Fila pausada para inspeção."))
        else:
            self.stdout.write(self.style.SUCCESS("Nenhum job órfão detectado."))
