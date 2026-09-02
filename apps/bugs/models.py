import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


class BugReport(models.Model):
    class Screen(models.TextChoices):
        LOGIN = "LOGIN", "Login"
        DASHBOARD = "DASHBOARD", "Dashboard Executivo"
        OPERATIONS = "OPERATIONS", "Operação de Hoje"
        DRIVERS = "DRIVERS", "Motoristas"
        DRIVER_PROFILE = "DRIVER_PROFILE", "Perfil do Motorista"
        PROOFS = "PROOFS", "Comprovantes Retidos"
        CLIENTS = "CLIENTS", "Clientes"
        REPORTS = "REPORTS", "Relatórios"
        SSW_IMPORTS = "SSW_IMPORTS", "Importações SSW"
        SSW_HISTORY = "SSW_HISTORY", "Histórico do Robô SSW"
        SETTINGS = "SETTINGS", "Configurações"
        GENERAL = "GENERAL", "Geral / Navegação"
        BACKEND = "BACKEND", "Backend / Banco / Regras"

    class Priority(models.TextChoices):
        P0 = "P0", "P0 — Bloqueador"
        P1 = "P1", "P1 — Crítico"
        P2 = "P2", "P2 — Importante"
        P3 = "P3", "P3 — Visual / Polimento"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto"
        ANALYSIS = "ANALYSIS", "Em análise"
        FIXING = "FIXING", "Em correção"
        RETEST = "RETEST", "Aguardando reteste"
        FAILED_RETEST = "FAILED_RETEST", "Falhou no reteste"
        RESOLVED = "RESOLVED", "Corrigido"
        CLOSED = "CLOSED", "Fechado"

    SCREEN_PATHS = {
        Screen.LOGIN: "/login/",
        Screen.DASHBOARD: "/dashboard/",
        Screen.OPERATIONS: "/operacao/hoje/",
        Screen.DRIVERS: "/motoristas/",
        Screen.DRIVER_PROFILE: "/motoristas/",
        Screen.PROOFS: "/comprovantes/",
        Screen.CLIENTS: "/clientes/",
        Screen.REPORTS: "/relatorios/",
        Screen.SSW_IMPORTS: "/ssw/importacoes/",
        Screen.SSW_HISTORY: "/ssw/historico/",
        Screen.SETTINGS: "/configuracoes/",
        Screen.GENERAL: "",
        Screen.BACKEND: "",
    }

    screen = models.CharField(max_length=30, choices=Screen.choices, db_index=True)
    screen_path = models.CharField(max_length=180, blank=True)
    title = models.CharField(max_length=180)
    priority = models.CharField(max_length=2, choices=Priority.choices, default=Priority.P2, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)

    description = models.TextField(blank=True)
    current_result = models.TextField(blank=True)
    expected_result = models.TextField(blank=True)
    reproduction_steps = models.TextField(blank=True)
    technical_notes = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    retest_notes = models.TextField(blank=True)
    fixed_version = models.CharField(max_length=30, blank=True, db_index=True)

    attachment = models.FileField(
        upload_to="bug_reports/%Y/%m/",
        blank=True,
        validators=[FileExtensionValidator(["png", "jpg", "jpeg", "webp", "pdf", "txt", "log"])],
    )
    app_version = models.CharField(max_length=30, blank=True)
    browser_info = models.CharField(max_length=250, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="bugs_created",
        on_delete=models.SET_NULL,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="bugs_assigned",
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["screen", "status"]),
            models.Index(fields=["priority", "status"]),
        ]
        verbose_name = "Bug"
        verbose_name_plural = "Caderno de Bugs"

    def __str__(self):
        return f"{self.priority} #{self.pk or '-'} — {self.title}"

    @property
    def screen_url(self):
        return self.screen_path or self.SCREEN_PATHS.get(self.screen, "")

    @property
    def is_open(self):
        return self.status not in {self.Status.RESOLVED, self.Status.CLOSED}

    def save(self, *args, **kwargs):
        if not self.screen_path:
            self.screen_path = self.SCREEN_PATHS.get(self.screen, "")
        if self.status in {self.Status.RESOLVED, self.Status.CLOSED}:
            if not self.resolved_at:
                self.resolved_at = timezone.now()
        else:
            self.resolved_at = None
        super().save(*args, **kwargs)

class BugExchangeReference(models.Model):
    bug = models.OneToOneField(
        BugReport,
        related_name="exchange_reference",
        on_delete=models.CASCADE,
    )
    sync_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Referência de troca de bug"
        verbose_name_plural = "Referências de troca de bugs"

    def __str__(self):
        return f"{self.sync_id} -> Bug #{self.bug_id}"

