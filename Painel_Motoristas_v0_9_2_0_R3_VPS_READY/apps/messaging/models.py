from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.drivers.models import Driver
from apps.operations.models import Manifest


class WhatsAppMessage(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        SENDING = "SENDING", "Enviando"
        SENT = "SENT", "Enviado"
        FAILED = "FAILED", "Falhou"
        CANCELED = "CANCELED", "Cancelado"

    class Kind(models.TextChoices):
        DAILY = "DAILY", "Operação do dia"
        MANIFEST = "MANIFEST", "Manifesto/Romaneio"
        MANUAL = "MANUAL", "Manual"

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="whatsapp_messages")
    manifest = models.ForeignKey(Manifest, null=True, blank=True, on_delete=models.SET_NULL, related_name="whatsapp_messages")
    operation_date = models.DateField(db_index=True)
    phone = models.CharField(max_length=20)
    portal_url = models.TextField(blank=True)
    body = models.TextField()
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.DAILY, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    error = models.TextField(blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="whatsapp_messages_created")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="messaging_w_status_36a147_idx"),
            models.Index(fields=["operation_date", "driver"], name="messaging_w_operati_7db751_idx"),
        ]

    def mark_sending(self):
        self.status = self.Status.SENDING
        self.started_at = timezone.now()
        self.attempt_count += 1
        self.error = ""
        self.save(update_fields=["status", "started_at", "attempt_count", "error"])

    def mark_sent(self):
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.error = ""
        self.save(update_fields=["status", "sent_at", "error"])

    def mark_failed(self, error):
        self.status = self.Status.FAILED
        self.error = str(error or "Falha desconhecida")[:2000]
        self.save(update_fields=["status", "error"])
