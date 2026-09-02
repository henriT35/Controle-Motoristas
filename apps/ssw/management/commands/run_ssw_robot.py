from django.core.management.base import BaseCommand, CommandError

from apps.ssw.robot_service import execute_robot_import


class Command(BaseCommand):
    help = "Executa um ImportRun usando a API run_job do robô SSW homologado."

    def add_arguments(self, parser):
        parser.add_argument("run_id", type=int)

    def handle(self, *args, **options):
        try:
            run_id = execute_robot_import(options["run_id"])
            self.stdout.write(self.style.SUCCESS(f"ImportRun #{run_id} finalizado pelo fluxo Painel/robô."))
        except Exception as exc:
            raise CommandError(str(exc)) from exc
