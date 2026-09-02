from django.conf import settings
from django.db import models
from apps.operations.models import CTe, Manifest
from apps.clients.models import Client, ClientAddress
from apps.drivers.models import Driver


class RetainedProof(models.Model):
    class Status(models.TextChoices):
        WAITING = "AGUARDANDO_RETIRADA", "Aguardando retirada"
        AVAILABLE = "DISPONIVEL_HOJE", "Disponível hoje"
        RECOVERING = "EM_RECUPERACAO", "Em recuperação"
        AWAITING_VALIDATION = "AGUARDANDO_VALIDACAO", "Aguardando validação"
        RECOVERED = "RECUPERADO", "Recuperado"
        CANCELED = "CANCELADO", "Cancelado"

    cte = models.OneToOneField(CTe, on_delete=models.CASCADE, related_name="retained_proof")
    invoice_number = models.CharField(max_length=80, blank=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="retained_proofs")
    address = models.ForeignKey(ClientAddress, null=True, blank=True, on_delete=models.SET_NULL)
    original_driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="originated_retained_proofs")
    original_manifest = models.ForeignKey(Manifest, null=True, blank=True, on_delete=models.SET_NULL)
    retained_at = models.DateTimeField(db_index=True)
    freight_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    merchandise_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    weight_kg = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    volumes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.WAITING, db_index=True)
    recovered_at = models.DateTimeField(null=True, blank=True)
    # Quem originou a retenção e quem recuperou são fatos independentes.
    recovery_driver = models.ForeignKey(Driver, null=True, blank=True, on_delete=models.SET_NULL, related_name="recovered_proofs")
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "retained_at"]),
            models.Index(fields=["client", "status"]),
            models.Index(fields=["original_driver", "retained_at"]),
        ]

    @property
    def days_retained(self):
        from django.utils import timezone
        end = self.recovered_at.date() if self.recovered_at else timezone.localdate()
        return max((end - self.retained_at.date()).days, 0)

    @property
    def is_critical(self):
        from apps.core.models import SystemSettings
        return self.status in {
            self.Status.WAITING,
            self.Status.AVAILABLE,
            self.Status.RECOVERING,
            self.Status.AWAITING_VALIDATION,
        } and self.days_retained > SystemSettings.load().critical_days


class ProofRecoverySubmission(models.Model):
    """Evidência auditável de recuperação.

    O portal cria PENDING. O coordenador pode registrar uma recuperação já
    APPROVED ou validar/rejeitar uma submissão do motorista.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Aguardando validação"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Rejeitada"

    class Source(models.TextChoices):
        COORDINATOR = "COORDINATOR", "Coordenador"
        DRIVER_PORTAL = "DRIVER_PORTAL", "Portal do motorista"

    proof = models.ForeignKey(RetainedProof, on_delete=models.CASCADE, related_name="recovery_submissions")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="proof_recovery_submissions")
    recovered_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.COORDINATOR)
    evidence = models.FileField(
        upload_to="proof_recovery/%Y/%m/",
        blank=True,
    )
    note = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proof_recovery_submissions_created",
    )
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="proof_recovery_submissions_validated",
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    validation_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["status", "submitted_at"]),
            models.Index(fields=["driver", "recovered_at"]),
        ]
