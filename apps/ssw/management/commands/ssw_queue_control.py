from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ssw.diagnostics import pause_queue, queue_pause_state, resume_queue
from apps.ssw.dispatch import dispatch_next_robot_run


class Command(BaseCommand):
    help = "Consulta, pausa ou retoma a fila do Robô SSW."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["status", "pause", "resume"])
        parser.add_argument("--reason", default="Pausa manual")

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        action = options["action"]
        if action == "status":
            state = queue_pause_state(base_dir)
            if state.get("paused"):
                self.stdout.write(self.style.WARNING(f"PAUSADA | {state}"))
            else:
                self.stdout.write(self.style.SUCCESS("ATIVA"))
            return
        if action == "resume":
            resume_queue(base_dir)
            dispatched = False
            try:
                dispatched = dispatch_next_robot_run()
            except Exception as exc:
                self.stderr.write(f"Fila liberada, mas o despacho seguinte falhou: {exc}")
            self.stdout.write(self.style.SUCCESS(f"Fila SSW retomada. Próximo job despachado: {'SIM' if dispatched else 'NÃO'}"))
            return
        pause_queue(base_dir, reason=options["reason"], execution_id="manual", error_code="MANUAL_PAUSE")
        self.stdout.write(self.style.WARNING("Fila SSW pausada manualmente."))
