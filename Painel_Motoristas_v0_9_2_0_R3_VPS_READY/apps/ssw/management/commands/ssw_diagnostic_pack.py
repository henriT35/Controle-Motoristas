from pathlib import Path
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ssw.diagnostics import build_diagnostic_zip


class Command(BaseCommand):
    help = "Gera ZIP sanitizado com os artefatos técnicos de uma execution_id."

    def add_arguments(self, parser):
        parser.add_argument("execution_id")
        parser.add_argument("--output", default=None)

    def handle(self, *args, **options):
        try:
            generated = build_diagnostic_zip(Path(settings.BASE_DIR), options["execution_id"])
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        output = options.get("output")
        if output:
            target = Path(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(generated, target)
            generated = target
        self.stdout.write(self.style.SUCCESS(str(generated)))
