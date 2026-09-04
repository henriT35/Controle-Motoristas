from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Health check leve do Painel Motoristas."

    def handle(self, *args, **options):
        checks = []
        checks.append(("Django", True, "configuração carregada"))
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            checks.append(("Banco", True, connection.vendor))
        except Exception as exc:
            checks.append(("Banco", False, str(exc)))

        try:
            executor = MigrationExecutor(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
            checks.append(("Migrations", not pending, f"{len(pending)} pendente(s)"))
        except Exception as exc:
            checks.append(("Migrations", False, str(exc)))

        robot_dir = Path(settings.SSW_ROBOT_DIR)
        core = robot_dir / "robot_ssw" / "worker.py"
        checks.append(("Core robô", core.exists(), str(core)))
        try:
            import playwright  # noqa: F401
            checks.append(("Playwright", True, "import OK"))
        except Exception as exc:
            checks.append(("Playwright", False, str(exc)))

        self.stdout.write("\nPAINEL MOTORISTAS — HEALTH CHECK")
        self.stdout.write("=" * 52)
        failed = 0
        for name, ok, detail in checks:
            if not ok:
                failed += 1
            self.stdout.write(f"{name:14} {'OK' if ok else 'ERRO':5}  {detail}")
        if failed:
            raise SystemExit(1)
