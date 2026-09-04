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
        VERIFY = "VERIFICAR", "Verificar"
        TRACKING = "ACOMPANHANDO_SSW", "Acompanhando SSW"
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
    resolution_source = models.CharField(max_length=30, blank=True, db_index=True)
    last_ssw_code = models.CharField(max_length=20, blank=True)
    last_ssw_description = models.CharField(max_length=255, blank=True)
    last_ssw_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "retained_at"], name="proofs_reta_status_9c7988_idx"),
            models.Index(fields=["client", "status"], name="proofs_reta_client__1567c0_idx"),
            models.Index(fields=["original_driver", "retained_at"], name="proofs_reta_origina_855a85_idx"),
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
            self.Status.VERIFY,
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
            models.Index(fields=["status", "submitted_at"], name="proofs_proo_status_aeb59b_idx"),
            models.Index(fields=["driver", "recovered_at"], name="proofs_proo_driver__bc6882_idx"),
        ]


class ProofRetention(models.Model):
    """Evidência da retenção informada pelo motorista no momento da entrega.

    Não substitui RetainedProof: complementa o fato de origem com ressalva/foto e
    mantém motorista/romaneio originais imutáveis para auditoria.
    """
    proof = models.OneToOneField(RetainedProof, on_delete=models.CASCADE, related_name="retention_evidence")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="proof_retentions_reported")
    manifest = models.ForeignKey(Manifest, null=True, blank=True, on_delete=models.SET_NULL)
    retained_at = models.DateTimeField(db_index=True)
    evidence = models.FileField(upload_to="proof_retention/%Y/%m/", blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["driver", "retained_at"], name="proofs_proo_driver__05b467_idx")]


class ProofRetentionObligation(models.Model):
    """Obrigação de registrar ressalva quando ROM34 confirma retenção na tentativa.

    O marco de ativação da v0.9.2 impede penalização retroativa. Um ROM34 novo
    sem ProofRetention vira MISSED apenas após o encerramento da data operacional.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Aguardando encerramento"
        FULFILLED = "FULFILLED", "Ressalva registrada"
        MISSED = "MISSED", "Sem ressalva registrada"

    proof = models.ForeignKey(RetainedProof, on_delete=models.CASCADE, related_name="retention_obligations")
    movement = models.ForeignKey("operations.DeliveryMovement", on_delete=models.CASCADE, related_name="proof_retention_obligations")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="proof_retention_obligations")
    manifest = models.ForeignKey(Manifest, on_delete=models.PROTECT, related_name="proof_retention_obligations")
    operation_date = models.DateField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    missed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-operation_date", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["proof", "movement"], name="uniq_retention_obligation_attempt"),
        ]
        indexes = [
            models.Index(fields=["driver", "operation_date", "status"], name="proofs_retobl_driver_date_idx"),
            models.Index(fields=["status", "operation_date"], name="proofs_retobl_status_date_idx"),
        ]



class ProofPickupOpportunity(models.Model):
    """Registro persistente da oportunidade efetivamente apresentada ao motorista.

    EXACT é uma ação esperada e pode se tornar MISSED somente depois do encerramento
    da data operacional. GOLD é sempre voluntária e expira de forma neutra.
    """

    class Kind(models.TextChoices):
        EXACT = "EXACT", "Retirada exata"
        GOLD = "GOLD", "Oportunidade de ouro"

    class Status(models.TextChoices):
        PRESENTED = "PRESENTED", "Apresentada"
        RESPONDED = "RESPONDED", "Respondida"
        MISSED = "MISSED", "Sem manifestação"
        EXPIRED_NEUTRAL = "EXPIRED_NEUTRAL", "Encerrada sem impacto"
        CLOSED = "CLOSED", "Encerrada"

    class Source(models.TextChoices):
        PORTAL = "PORTAL", "Portal do motorista"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        SYSTEM = "SYSTEM", "Sistema"

    proof = models.ForeignKey(RetainedProof, on_delete=models.CASCADE, related_name="pickup_opportunities")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="proof_pickup_opportunities")
    manifest = models.ForeignKey(Manifest, on_delete=models.PROTECT, related_name="proof_pickup_opportunities")
    operation_date = models.DateField(db_index=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENTED, db_index=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.PORTAL)
    first_presented_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_presented_at = models.DateTimeField(auto_now=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=20, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-operation_date", "-first_presented_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["proof", "driver", "manifest", "operation_date", "kind"],
                name="uniq_pickup_opportunity_day",
            )
        ]
        indexes = [
            models.Index(fields=["driver", "operation_date", "kind"], name="proofs_opp_drv_date_kind_idx"),
            models.Index(fields=["status", "operation_date"], name="proofs_opp_status_date_idx"),
        ]


class ProofPickupAttempt(models.Model):
    class Kind(models.TextChoices):
        EXACT = "EXACT", "Retirada exata"
        GOLD = "GOLD", "Oportunidade de ouro"

    class Outcome(models.TextChoices):
        RECOVERED = "RECOVERED", "Retirei"
        NOT_RELEASED = "NOT_RELEASED", "Ainda não liberado"
        UNABLE = "UNABLE", "Não foi possível tentar"

    proof = models.ForeignKey(RetainedProof, on_delete=models.CASCADE, related_name="pickup_attempts")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="proof_pickup_attempts")
    manifest = models.ForeignKey(Manifest, null=True, blank=True, on_delete=models.SET_NULL, related_name="proof_pickup_attempts")
    operation_date = models.DateField(db_index=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, db_index=True)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, db_index=True)
    note = models.TextField(blank=True)
    evidence = models.FileField(upload_to="proof_attempts/%Y/%m/", blank=True)
    submission = models.OneToOneField(
        ProofRecoverySubmission, null=True, blank=True, on_delete=models.SET_NULL, related_name="pickup_attempt"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["proof", "driver", "manifest", "operation_date", "kind"],
                name="uniq_pickup_attempt_offer_day",
            )
        ]
        indexes = [
            models.Index(fields=["driver", "operation_date", "kind"], name="proofs_proo_driver__077d69_idx"),
            models.Index(fields=["proof", "outcome"], name="proofs_proo_proof_i_d8cc8e_idx"),
        ]
