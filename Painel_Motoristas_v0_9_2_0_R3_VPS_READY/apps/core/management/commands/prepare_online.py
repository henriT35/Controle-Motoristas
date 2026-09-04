from pathlib import Path
import os
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


DEFAULT_LOCAL_PASSWORD = "Painel@2026!"


def _saved_generated_password(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Senha:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        return ""
    return ""


class Command(BaseCommand):
    help = "Protege credenciais locais antes de expor o Painel pela Internet."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.getenv("LOCAL_ADMIN_USERNAME", "admin")
        user = User.objects.filter(username=username).first()
        if not user:
            raise CommandError(
                f"Administrador '{username}' não existe. Execute bootstrap_local primeiro."
            )

        credentials_path = Path(settings.BASE_DIR) / "local_data" / "ONLINE_ADMIN.txt"
        credentials_path.parent.mkdir(parents=True, exist_ok=True)
        saved_password = _saved_generated_password(credentials_path)

        if user.check_password(DEFAULT_LOCAL_PASSWORD):
            new_password = secrets.token_urlsafe(18)
            user.set_password(new_password)
            user.save(update_fields=["password"])
            credentials_path.write_text(
                "PAINEL MOTORISTAS - CREDENCIAL ONLINE\n"
                f"Usuario: {username}\n"
                f"Senha: {new_password}\n"
                "\nGerada automaticamente porque a senha local padrão não pode ser publicada.\n"
                "Se você alterar a senha no sistema, este arquivo deixa de ser a referência.\n",
                encoding="utf-8",
            )
            self.stdout.write(self.style.WARNING(
                "A senha padrão foi substituída automaticamente antes da publicação online."
            ))
            self.stdout.write(f"Credencial salva localmente em: {credentials_path}")
            return

        if saved_password and user.check_password(saved_password):
            self.stdout.write(self.style.SUCCESS(
                "A credencial online gerada anteriormente continua válida."
            ))
            return

        # O usuário já trocou a senha por conta própria. Não preserve um arquivo
        # com credencial antiga que poderia induzir a erro.
        if credentials_path.exists():
            try:
                credentials_path.unlink()
            except OSError:
                pass
        self.stdout.write(self.style.SUCCESS(
            "Credencial administrativa personalizada detectada; nenhuma senha foi alterada."
        ))
