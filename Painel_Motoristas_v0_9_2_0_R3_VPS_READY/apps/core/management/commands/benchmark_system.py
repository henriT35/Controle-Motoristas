from time import perf_counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.drivers.models import Driver


class Command(BaseCommand):
    help = "Mede tempo e queries das páginas críticas sem alterar dados."

    def add_arguments(self, parser):
        parser.add_argument("--repeat", type=int, default=3)

    def handle(self, *args, **options):
        repeat = max(options["repeat"], 1)
        user = get_user_model().objects.filter(is_superuser=True).first() or get_user_model().objects.filter(is_staff=True).first()
        if not user:
            self.stderr.write("Nenhum usuário admin/staff disponível. Execute bootstrap_local.")
            raise SystemExit(2)
        client = Client()
        client.force_login(user)
        urls = [
            ("Dashboard", "/dashboard/"),
            ("Operação Hoje", "/operacao/hoje/"),
            ("Motoristas", "/motoristas/"),
            ("Comprovantes", "/comprovantes/"),
            ("Clientes", "/clientes/"),
            ("Importações", "/ssw/importacoes/"),
            ("Histórico SSW", "/ssw/historico/"),
            ("Relatórios", "/relatorios/"),
            ("Caderno Bugs", "/bugs/"),
        ]
        driver = Driver.objects.order_by("pk").first()
        if driver:
            urls.append(("Perfil Motorista", f"/motoristas/{driver.pk}/"))

        self.stdout.write("\nPAINEL MOTORISTAS — BENCHMARK WEB")
        self.stdout.write("=" * 66)
        self.stdout.write(f"{'Página':22} {'melhor ms':>10} {'média ms':>10} {'queries':>10} {'status':>8}")
        for label, url in urls:
            times = []
            query_counts = []
            status = None
            for _ in range(repeat):
                with CaptureQueriesContext(connection) as ctx:
                    t0 = perf_counter()
                    response = client.get(url)
                    times.append((perf_counter() - t0) * 1000)
                    query_counts.append(len(ctx.captured_queries))
                    status = response.status_code
            self.stdout.write(f"{label:22} {min(times):10.1f} {sum(times)/len(times):10.1f} {min(query_counts):10d} {status:8d}")
