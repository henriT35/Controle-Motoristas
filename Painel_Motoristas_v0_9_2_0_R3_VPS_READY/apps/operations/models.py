from django.db import models
from apps.drivers.models import Driver, Vehicle
from apps.clients.models import Client, ClientAddress

class CTe(models.Model):
    ctrc = models.CharField(max_length=40, unique=True, db_index=True)
    invoice_number = models.CharField(max_length=80, blank=True, db_index=True)
    sender_name = models.CharField(max_length=220, blank=True)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="ctes")
    freight_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    merchandise_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    weight_kg = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    volumes = models.PositiveIntegerField(default=0)
    current_status = models.CharField(max_length=120, blank=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ctrc

class Manifest(models.Model):
    number = models.CharField(max_length=40, unique=True, db_index=True)
    date = models.DateField(db_index=True)
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="manifests")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=80, blank=True, db_index=True)

    def __str__(self):
        return self.number

class DeliveryMovement(models.Model):
    cte = models.ForeignKey(CTe, on_delete=models.CASCADE, related_name="movements")
    manifest = models.ForeignKey(Manifest, on_delete=models.CASCADE, related_name="movements")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="movements")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL)
    address = models.ForeignKey(ClientAddress, null=True, blank=True, on_delete=models.SET_NULL)
    movement_date = models.DateField(db_index=True)
    status = models.CharField(max_length=120, blank=True, db_index=True)
    occurrence_text = models.CharField(max_length=255, blank=True)
    attempt = models.PositiveSmallIntegerField(default=1)
    weight_kg = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    volumes = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cte", "manifest"], name="uniq_cte_manifest_movement"),
        ]
        indexes = [
            models.Index(fields=["movement_date", "driver"], name="operations__movemen_0bba38_idx"),
            models.Index(fields=["movement_date", "client"], name="operations__movemen_df1979_idx"),
        ]

class DeliveryOccurrence(models.Model):
    cte = models.ForeignKey(CTe, on_delete=models.CASCADE, related_name="occurrences")
    movement = models.ForeignKey(DeliveryMovement, null=True, blank=True, on_delete=models.SET_NULL, related_name="occurrences")
    code = models.CharField(max_length=20, blank=True, db_index=True)
    description = models.CharField(max_length=255, db_index=True)
    occurred_at = models.DateTimeField(null=True, blank=True, db_index=True)
    source = models.CharField(max_length=40, default="SSW")
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["code", "occurred_at"], name="operations__code_941cf6_idx"),
            models.Index(fields=["cte", "occurred_at"], name="operations__cte_id_625e3d_idx"),
            models.Index(fields=["movement", "occurred_at"], name="operations__movemen_80321e_idx"),
        ]
