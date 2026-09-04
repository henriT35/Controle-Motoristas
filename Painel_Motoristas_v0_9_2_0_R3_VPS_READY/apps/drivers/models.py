import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_driver_portal_token():
    # ~256 bits de entropia; não contém CPF, nome nem PK incremental.
    return secrets.token_urlsafe(32)


class Driver(models.Model):
    name = models.CharField(max_length=180, db_index=True)
    cpf = models.CharField(max_length=14, unique=True, db_index=True)
    active = models.BooleanField(default=True)
    # Registros de homologação/fictícios permanecem consultáveis, mas não entram
    # em rankings, médias e KPIs operacionais oficiais.
    is_test = models.BooleanField(default=False, db_index=True)
    whatsapp_phone = models.CharField(max_length=20, blank=True, db_index=True)
    whatsapp_enabled = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DriverPortalAccess(models.Model):
    """Acesso simplificado e revogável do motorista, sem login tradicional."""

    driver = models.OneToOneField(Driver, on_delete=models.CASCADE, related_name="portal_access")
    token = models.CharField(max_length=64, unique=True, db_index=True, default=generate_driver_portal_token, editable=False)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Acesso do portal do motorista"
        verbose_name_plural = "Acessos do portal dos motoristas"

    def rotate(self):
        self.token = generate_driver_portal_token()
        self.rotated_at = timezone.now()
        self.active = True
        self.save(update_fields=["token", "rotated_at", "active"])
        return self.token


class Vehicle(models.Model):
    plate = models.CharField(max_length=8, unique=True, db_index=True)
    description = models.CharField(max_length=120, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.plate


class DriverPortalAccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Rejeitada"

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="portal_access_requests")
    requested_phone = models.CharField(max_length=20, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="driver_portal_access_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)
    generated_access = models.ForeignKey(
        DriverPortalAccess, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="approved_requests",
    )
    sent_via_whatsapp = models.BooleanField(default=False)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["status", "requested_at"], name="drivers_dri_status_e3c5d8_idx"),
            models.Index(fields=["driver", "status"], name="drivers_dri_driver__4f7925_idx"),
        ]

    def __str__(self):
        return f"{self.driver} — {self.get_status_display()}"


class DriverQualityEvent(models.Model):
    """Validação humana de ROM13 por tentativa.

    O evento nasce PENDING e nunca afeta a Nota Geral antes de uma decisão
    explícita do coordenador. Uma nova tentativa com novo ROM13 gera novo evento;
    importações repetidas da mesma tentativa permanecem idempotentes.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente de validação"
        DRIVER_RESPONSIBLE = "DRIVER_RESPONSIBLE", "Responsabilidade do motorista"
        NOT_RESPONSIBLE = "NOT_RESPONSIBLE", "Não foi responsabilidade do motorista"
        VERIFY = "VERIFY", "Não foi possível determinar"

    movement = models.ForeignKey("operations.DeliveryMovement", on_delete=models.CASCADE, related_name="quality_events")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="quality_events")
    cte = models.ForeignKey("operations.CTe", on_delete=models.PROTECT, related_name="driver_quality_events")
    manifest = models.ForeignKey("operations.Manifest", on_delete=models.PROTECT, related_name="driver_quality_events")
    client = models.ForeignKey("clients.Client", null=True, blank=True, on_delete=models.SET_NULL, related_name="driver_quality_events")
    source_occurrence = models.ForeignKey("operations.DeliveryOccurrence", null=True, blank=True, on_delete=models.SET_NULL, related_name="quality_review_events")
    code = models.CharField(max_length=20, default="13", db_index=True)
    operation_date = models.DateField(db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING, db_index=True)
    visible_reason = models.TextField(blank=True)
    internal_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="driver_quality_events_reviewed"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reopened_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-operation_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["movement", "code"], name="uniq_quality_event_movement_code"),
        ]
        indexes = [
            models.Index(fields=["status", "operation_date"], name="drivers_qe_status_date_idx"),
            models.Index(fields=["driver", "operation_date"], name="drivers_qe_driver_date_idx"),
        ]

    @property
    def affects_quality(self):
        return self.status == self.Status.DRIVER_RESPONSIBLE

    def __str__(self):
        return f"ROM{self.code} · {self.driver} · {self.manifest} · {self.get_status_display()}"


class DriverScoreSnapshot(models.Model):
    """Fotografia auditável da Nota Geral V3.

    Não substitui os fatos que originam a nota (ROM13, oportunidades e
    recuperações). Apenas guarda a fotografia calculada para que o motorista
    consiga entender a evolução sem transformar o ranking em uma caixa-preta.
    """

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="score_snapshots")
    score_date = models.DateField(db_index=True)
    period_start = models.DateField()
    period_end = models.DateField()
    general_score = models.DecimalField(max_digits=5, decimal_places=2)
    proof_management_score = models.DecimalField(max_digits=5, decimal_places=2)
    operational_quality_score = models.DecimalField(max_digits=5, decimal_places=2)
    regularity_score = models.DecimalField(max_digits=5, decimal_places=2)
    recovery_bonus = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    attempts = models.PositiveIntegerField(default=0)
    eligible = models.BooleanField(default=False)
    breakdown = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score_date", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["driver", "score_date", "period_start", "period_end"],
                name="uniq_driver_score_snapshot_period",
            )
        ]
        indexes = [
            models.Index(fields=["driver", "score_date"], name="drivers_score_driver_date_idx"),
        ]

    def __str__(self):
        return f"{self.driver} · {self.score_date:%d/%m/%Y} · {self.general_score}"
