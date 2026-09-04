from django.core.management.base import BaseCommand
from apps.proofs.services import reconcile_retained_proofs


class Command(BaseCommand):
    help = "Reconcilia comprovantes retidos pelo estado consolidado atual do CTRC. Padrão: dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Aplica as alterações. Sem esta flag é dry-run.")
        parser.add_argument("--dry-run", action="store_true", help="Mantido por clareza; é o comportamento padrão.")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--quiet", action="store_true")

    def handle(self, *args, **options):
        result = reconcile_retained_proofs(apply=options["apply"], limit=options.get("limit"))
        if not options["quiet"]:
            mode = "APLICADO" if result["applied"] else "DRY-RUN"
            self.stdout.write(self.style.SUCCESS(f"{mode}: {result}"))
