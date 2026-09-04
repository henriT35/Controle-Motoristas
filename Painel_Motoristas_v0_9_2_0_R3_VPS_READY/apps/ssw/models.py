from django.conf import settings
from django.db import models

class ImportRun(models.Model):
    class Kind(models.TextChoices):
        FAST = "FAST", "Atualização rápida"
        MONTH = "MONTH", "Reconciliação mensal"
        HISTORY = "HISTORY", "Importação histórica"
        MANUAL = "MANUAL", "Manual"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Na fila"
        DISPATCHED = "DISPATCHED", "Enviado ao robô"
        RUNNING = "RUNNING", "Em andamento"
        SUCCESS = "SUCCESS", "Sucesso"
        WARNING = "WARNING", "Aviso"
        ERROR = "ERROR", "Erro"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    source_file = models.CharField(max_length=255, blank=True)
    new_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    unchanged_count = models.PositiveIntegerField(default=0)
    ignored_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    parse_seconds = models.FloatField(default=0, db_default=0)
    normalize_seconds = models.FloatField(default=0, db_default=0)
    preload_seconds = models.FloatField(default=0, db_default=0)
    compare_seconds = models.FloatField(default=0, db_default=0)
    database_seconds = models.FloatField(default=0, db_default=0)
    postprocess_seconds = models.FloatField(default=0, db_default=0)
    total_seconds = models.FloatField(default=0, db_default=0)
    rows_read = models.PositiveIntegerField(default=0, db_default=0)
    rows_valid = models.PositiveIntegerField(default=0, db_default=0)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"], name="ssw_importr_status_140239_idx"),
            models.Index(fields=["kind", "start_date", "end_date"], name="ssw_importr_kind_816ee4_idx"),
        ]

    @property
    def duration_seconds(self):
        if not self.started_at or not self.finished_at:
            return None
        return max((self.finished_at - self.started_at).total_seconds(), 0)


class ImportStep(models.Model):
    run = models.ForeignKey(ImportRun, on_delete=models.CASCADE, related_name="steps")
    name = models.CharField(max_length=80)
    status = models.CharField(max_length=20, default="PENDING")
    occurred_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True)

