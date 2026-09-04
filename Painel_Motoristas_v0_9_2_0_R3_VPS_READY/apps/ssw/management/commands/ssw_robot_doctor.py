from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ssw.robot_bridge import BRIDGE_BUILD, check_robot_ready, robot_root
from apps.ssw.diagnostics import queue_pause_state


class Command(BaseCommand):
    help = "Diagnóstico do Robô SSW homologado integrado ao Painel Motoristas."

    def handle(self, *args, **options):
        root = robot_root()
        core = root / "robot_ssw" / "worker.py"
        env_file = root / ".env"
        self.stdout.write("=" * 66)
        self.stdout.write(" DIAGNÓSTICO - ROBÔ SSW HOMOLOGADO / PAINEL MOTORISTAS")
        self.stdout.write("=" * 66)
        self.stdout.write(f"Bridge carregado     : {BRIDGE_BUILD}")
        self.stdout.write(f"Robô habilitado      : {getattr(settings, 'SSW_ROBOT_ENABLED', False)}")
        self.stdout.write(f"Diretório            : {root}")
        self.stdout.write(f"Core homologado      : {'SIM' if core.exists() else 'NÃO'}")
        self.stdout.write(f"API esperada         : robot_ssw.run_job")
        self.stdout.write(f".env do robô         : {'SIM' if env_file.exists() else 'NÃO'}")
        self.stdout.write(f"Unidade              : {getattr(settings, 'SSW_ROBOT_UNIT', 'BEL')}")
        self.stdout.write(f"Opção                : {getattr(settings, 'SSW_ROBOT_OPTION', '036')}")
        self.stdout.write(f"Excel                : {getattr(settings, 'SSW_ROBOT_EXCEL', 'S')}")
        self.stdout.write(f"Dispatch             : {getattr(settings, 'SSW_ROBOT_DISPATCH_MODE', 'local_process')}")
        self.stdout.write(f"Timeout worker       : {getattr(settings, 'SSW_ROBOT_TIMEOUT_SECONDS', 900)}s")
        self.stdout.write(f"Heartbeat watchdog   : {getattr(settings, 'SSW_ROBOT_HEARTBEAT_SECONDS', 10)}s")
        state = queue_pause_state(Path(settings.BASE_DIR))
        self.stdout.write(f"Fila de automação    : {'PAUSADA' if state.get('paused') else 'ATIVA'}")
        if state.get("paused"):
            self.stdout.write(f"Motivo da pausa      : {state.get('error_code', '-')} | {state.get('reason', '-')}")
        ready, detail = check_robot_ready(launch_browser=True)
        self.stdout.write(f"Pronto para executar : {'SIM' if ready else 'NÃO'}")
        self.stdout.write(f"Diagnóstico          : {detail}")
        self.stdout.write("Credenciais não são exibidas.")
