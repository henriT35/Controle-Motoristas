from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.ssw.importer import import_ssw_delivery_file
from apps.ssw.models import ImportRun


class Command(BaseCommand):
    help = "Importa um relatório de entregas exportado pelo SSW (.sswweb/.csv)."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Caminho do arquivo dentro do ambiente Django")
        parser.add_argument(
            "--kind",
            default=ImportRun.Kind.MANUAL,
            choices=[choice[0] for choice in ImportRun.Kind.choices],
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")
        run, stats = import_ssw_delivery_file(path, kind=options["kind"])
        self.stdout.write(self.style.SUCCESS(
            f"Importação #{run.pk} concluída. "
            f"Novos={stats.new}, Atualizados={stats.updated}, "
            f"Sem alteração={stats.unchanged}, Ignorados={stats.ignored}, "
            f"Retidos criados={stats.proofs_created}."
        ))
