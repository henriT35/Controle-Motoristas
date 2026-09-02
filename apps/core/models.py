from datetime import time
from django.db import models
from django.core.cache import cache


class SystemSettings(models.Model):
    """Configuração singleton do produto.

    Mantém regras operacionais que precisam ser persistentes e auditáveis.
    """

    period_default = models.CharField(max_length=20, default="month")
    timezone_name = models.CharField(max_length=64, default="America/Belem")
    currency = models.CharField(max_length=8, default="BRL")
    decimal_places = models.PositiveSmallIntegerField(default=2)

    sync_frequency_hours = models.PositiveSmallIntegerField(default=3)
    recent_window_days = models.PositiveSmallIntegerField(default=15)
    monthly_reconcile_time = models.TimeField(default=time(23, 0))
    log_retention_days = models.PositiveIntegerField(default=90)

    critical_days = models.PositiveSmallIntegerField(default=15)
    alert_min_days = models.PositiveSmallIntegerField(default=7)
    minimum_sample = models.PositiveIntegerField(default=20)
    proof_sla_days = models.PositiveSmallIntegerField(default=7)

    # Motor de avaliação V2. A nota permanece explicitamente em modo SIMULAÇÃO
    # até homologação operacional dos pesos. Produtividade é exibida separada.
    driver_score_delivery_weight = models.DecimalField(max_digits=5, decimal_places=2, default=35)
    driver_score_clean_weight = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    driver_score_retention_weight = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    driver_score_time_window_weight = models.DecimalField(max_digits=5, decimal_places=2, default=15)
    driver_score_proof_weight = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    driver_score_recovery_weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    driver_rank_min_attempts = models.PositiveIntegerField(default=30)

    operational_weight = models.DecimalField(max_digits=5, decimal_places=2, default=60)
    effort_weight = models.DecimalField(max_digits=5, decimal_places=2, default=40)
    effort_movements_weight = models.DecimalField(max_digits=5, decimal_places=2, default=35)
    effort_stops_weight = models.DecimalField(max_digits=5, decimal_places=2, default=25)
    effort_manifests_weight = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    effort_weight_kg_weight = models.DecimalField(max_digits=5, decimal_places=2, default=20)

    theme = models.CharField(max_length=20, default="dark")
    accent = models.CharField(max_length=20, default="blue")
    density = models.CharField(max_length=20, default="comfortable")

    notification_emails = models.TextField(blank=True)
    email_notifications_enabled = models.BooleanField(default=False)
    daily_summary_enabled = models.BooleanField(default=False)
    daily_summary_time = models.TimeField(default=time(8, 0))

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do sistema"
        verbose_name_plural = "Configurações do sistema"

    def __str__(self):
        return "Configuração do Painel Motoristas"

    CACHE_KEY = "system_settings:v1"

    @classmethod
    def load(cls):
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 60)
        return obj

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)
        return result

    def delete(self, *args, **kwargs):
        cache.delete(self.CACHE_KEY)
        return super().delete(*args, **kwargs)
