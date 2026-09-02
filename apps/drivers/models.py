import secrets

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
