import tracemalloc
from pathlib import Path
from time import perf_counter

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.ssw.importer import import_ssw_delivery_file


class Command(BaseCommand):
    help = "Benchmark do importador SSW. Por padrão faz rollback ao final."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--repeat", type=int, default=1)
        parser.add_argument("--commit", action="store_true", help="Persiste a execução; padrão é rollback.")

    def handle(self, *args, **options):
        path = Path(options["file"]).resolve()
        if not path.exists():
            self.stderr.write(f"Arquivo não encontrado: {path}")
            raise SystemExit(2)
        repeat = max(options["repeat"], 1)
        self.stdout.write("\nBENCHMARK IMPORTADOR SSW")
        self.stdout.write("=" * 62)
        results = []
        for idx in range(1, repeat + 1):
            tracemalloc.start()
            with CaptureQueriesContext(connection) as ctx:
                t0 = perf_counter()
                try:
                    with transaction.atomic():
                        run, stats = import_ssw_delivery_file(path)
                        if not options["commit"]:
                            transaction.set_rollback(True)
                finally:
                    elapsed = perf_counter() - t0
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            results.append((elapsed, len(ctx.captured_queries), peak, stats, run))
            self.stdout.write(
                f"#{idx}: {elapsed:.3f}s | {len(ctx.captured_queries)} queries | "
                f"pico {peak/1024/1024:.1f} MiB | linhas {stats.rows} | novos {stats.new} | "
                f"atualizados {stats.updated} | iguais {stats.unchanged}"
            )
            self.stdout.write(
                "    etapas: "
                f"leitura {getattr(run, 'parse_seconds', 0):.3f}s | "
                f"normalizacao {getattr(run, 'normalize_seconds', 0):.3f}s | "
                f"preload {getattr(run, 'preload_seconds', 0):.3f}s | "
                f"comparacao {getattr(run, 'compare_seconds', 0):.3f}s | "
                f"banco {getattr(run, 'database_seconds', 0):.3f}s | "
                f"pos {getattr(run, 'postprocess_seconds', 0):.3f}s"
            )
        self.stdout.write("-" * 62)
        self.stdout.write(
            f"Melhor: {min(x[0] for x in results):.3f}s | Média: {sum(x[0] for x in results)/len(results):.3f}s | "
            f"Menor queries: {min(x[1] for x in results)}"
        )
