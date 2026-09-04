from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.ssw.importer import import_ssw_delivery_file
from apps.ssw.models import ImportRun
from apps.ssw.parsers import read_ssw_delivery_file


class Command(BaseCommand):
    help = "Importa em lote todos os relatórios SSW (.sswweb/.csv) de uma pasta, em ordem cronológica."

    def add_arguments(self, parser):
        parser.add_argument("folder", help="Pasta com relatórios mensais do SSW")
        parser.add_argument(
            "--kind",
            default=ImportRun.Kind.MANUAL,
            choices=[choice[0] for choice in ImportRun.Kind.choices],
        )
        parser.add_argument(
            "--stop-on-error",
            action="store_true",
            help="Interrompe no primeiro arquivo com erro. Por padrão o lote continua.",
        )

    def handle(self, *args, **options):
        folder = Path(options["folder"])
        if not folder.exists() or not folder.is_dir():
            raise CommandError(f"Pasta não encontrada: {folder}")

        files = [
            p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in {".sswweb", ".csv"}
        ]
        if not files:
            raise CommandError("Nenhum arquivo .sswweb/.csv encontrado na pasta.")

        sortable = []
        for path in files:
            try:
                parsed = read_ssw_delivery_file(path)
                key = (parsed.period_start or parsed.period_end, parsed.period_end or parsed.period_start, path.name.lower())
            except Exception:
                key = (None, None, path.name.lower())
            # Arquivos válidos/cronológicos primeiro; inválidos ficam no fim para registrar erro.
            sortable.append((key, path))
        sortable.sort(key=lambda item: (item[0][0] is None, item[0][0] or "9999", item[0][1] or "9999", item[0][2]))

        totals = {"files": len(files), "ok": 0, "error": 0, "new": 0, "updated": 0, "unchanged": 0, "ignored": 0, "proofs": 0}
        for index, (_key, path) in enumerate(sortable, start=1):
            self.stdout.write(f"[{index}/{len(files)}] {path.name}")
            try:
                _run, stats = import_ssw_delivery_file(path, kind=options["kind"])
                totals["ok"] += 1
                totals["new"] += stats.new
                totals["updated"] += stats.updated
                totals["unchanged"] += stats.unchanged
                totals["ignored"] += stats.ignored
                totals["proofs"] += stats.proofs_created
                self.stdout.write(self.style.SUCCESS(
                    f"  OK — novos={stats.new}, atualizados={stats.updated}, sem alteração={stats.unchanged}, retidos criados={stats.proofs_created}"
                ))
            except Exception as exc:
                totals["error"] += 1
                self.stderr.write(self.style.ERROR(f"  ERRO — {exc}"))
                if options["stop_on_error"]:
                    raise CommandError(f"Lote interrompido em {path.name}") from exc

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "LOTE CONCLUÍDO — "
            f"arquivos={totals['files']}, sucesso={totals['ok']}, erros={totals['error']}, "
            f"novos={totals['new']}, atualizados={totals['updated']}, "
            f"sem alteração={totals['unchanged']}, ignorados={totals['ignored']}, "
            f"retidos criados={totals['proofs']}"
        ))
        if totals["error"]:
            raise CommandError(f"O lote terminou com {totals['error']} arquivo(s) com erro. Os demais foram preservados.")
