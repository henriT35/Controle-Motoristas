from django.db import migrations, models
import django.db.models.deletion
import apps.drivers.models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Driver",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(db_index=True, max_length=180)),
                ("cpf", models.CharField(db_index=True, max_length=14, unique=True)),
                ("active", models.BooleanField(default=True)),
                ("is_test", models.BooleanField(db_index=True, default=False)),
                ("whatsapp_phone", models.CharField(blank=True, db_index=True, max_length=20)),
                ("whatsapp_enabled", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering":["name"]},
        ),
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("plate", models.CharField(db_index=True, max_length=8, unique=True)),
                ("description", models.CharField(blank=True, max_length=120)),
                ("active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="DriverPortalAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(db_index=True, default=apps.drivers.models.generate_driver_portal_token, editable=False, max_length=64, unique=True)),
                ("active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("driver", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="portal_access", to="drivers.driver")),
            ],
            options={"verbose_name":"Acesso do portal do motorista","verbose_name_plural":"Acessos do portal dos motoristas"},
        ),
    ]
