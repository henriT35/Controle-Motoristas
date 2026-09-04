from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Client",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(db_index=True, max_length=220)),
                ("cnpj", models.CharField(blank=True, db_index=True, max_length=18)),
                ("active", models.BooleanField(default=True)),
                ("proof_required_for_payment", models.BooleanField(db_index=True, default=False)),
                ("proof_payment_note", models.CharField(blank=True, max_length=255)),
                ("first_delivery_at", models.DateField(blank=True, null=True)),
                ("last_delivery_at", models.DateField(blank=True, null=True)),
            ],
            options={"constraints":[models.UniqueConstraint(fields=("cnpj","name"), name="uniq_client_cnpj_name")]},
        ),
        migrations.CreateModel(
            name="ClientAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("street", models.CharField(max_length=255)),
                ("district", models.CharField(blank=True, db_index=True, max_length=120)),
                ("postal_code", models.CharField(blank=True, db_index=True, max_length=10)),
                ("city", models.CharField(db_index=True, max_length=120)),
                ("state", models.CharField(blank=True, max_length=2)),
                ("normalized_address", models.CharField(db_index=True, max_length=400)),
                ("latitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("longitude", models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="clients.client")),
            ],
            options={"constraints":[models.UniqueConstraint(fields=("client","normalized_address"), name="uniq_client_normalized_address")]},
        ),
    ]
