from django.db import models

class Client(models.Model):
    name = models.CharField(max_length=220, db_index=True)
    cnpj = models.CharField(max_length=18, blank=True, db_index=True)
    active = models.BooleanField(default=True)
    proof_required_for_payment = models.BooleanField(default=False, db_index=True)
    proof_payment_note = models.CharField(max_length=255, blank=True)
    first_delivery_at = models.DateField(null=True, blank=True)
    last_delivery_at = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cnpj", "name"], name="uniq_client_cnpj_name")
        ]

    def __str__(self):
        return self.name

class ClientAddress(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="addresses")
    street = models.CharField(max_length=255)
    district = models.CharField(max_length=120, blank=True, db_index=True)
    postal_code = models.CharField(max_length=10, blank=True, db_index=True)
    city = models.CharField(max_length=120, db_index=True)
    state = models.CharField(max_length=2, blank=True)
    normalized_address = models.CharField(max_length=400, db_index=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["client", "normalized_address"], name="uniq_client_normalized_address")
        ]

    def __str__(self):
        return f"{self.client} — {self.street}"
