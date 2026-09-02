import os
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Prepara o ambiente local e cria o administrador inicial se necessário."

    def handle(self, *args, **options):
        User = get_user_model()
        for group_name in ("Coordenador", "Analista"):
            Group.objects.get_or_create(name=group_name)
        username = os.getenv("LOCAL_ADMIN_USERNAME", "admin")
        password = os.getenv("LOCAL_ADMIN_PASSWORD", "Painel@2026!")
        email = os.getenv("LOCAL_ADMIN_EMAIL", "admin@localhost")

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )

        changed = False
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if created:
            user.set_password(password)
            changed = True
        if changed:
            user.save()


        # Upload manual roda dentro do processo Django local. Se o servidor foi
        # encerrado no meio da importação, nenhum worker externo poderá concluir
        # aquele MANUAL. Marcar como erro evita PROCESSING eterno após reinício.
        try:
            from apps.ssw.models import ImportRun
            stale_manual = ImportRun.objects.filter(
                kind=ImportRun.Kind.MANUAL,
                status=ImportRun.Status.RUNNING,
            )
            recovered = stale_manual.update(
                status=ImportRun.Status.ERROR,
                finished_at=timezone.now(),
                error_count=1,
                message="Importação manual interrompida por reinício do servidor. Reprocesse o arquivo.",
            )
            if recovered:
                self.stdout.write(self.style.WARNING(
                    f"{recovered} importação(ões) manual(is) interrompida(s) foram liberadas para reprocessamento."
                ))
        except Exception as exc:
            self.stderr.write(f"Aviso: não foi possível reconciliar ImportRun interrompido: {exc}")

        if created:
            self.stdout.write(self.style.SUCCESS(f"Administrador local criado: {username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Administrador local já existe: {username}"))
