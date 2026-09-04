from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [("clients","0001_initial"),("drivers","0001_initial")]
    operations = [
        migrations.CreateModel(
            name="CTe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ctrc", models.CharField(db_index=True, max_length=40, unique=True)),
                ("invoice_number", models.CharField(blank=True, db_index=True, max_length=80)),
                ("sender_name", models.CharField(blank=True, max_length=220)),
                ("freight_value", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("merchandise_value", models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ("weight_kg", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("volumes", models.PositiveIntegerField(default=0)),
                ("current_status", models.CharField(blank=True, db_index=True, max_length=120)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("client", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ctes", to="clients.client")),
            ],
        ),
        migrations.CreateModel(
            name="Manifest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(db_index=True, max_length=40, unique=True)),
                ("date", models.DateField(db_index=True)),
                ("status", models.CharField(blank=True, db_index=True, max_length=80)),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="manifests", to="drivers.driver")),
                ("vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="drivers.vehicle")),
            ],
        ),
        migrations.CreateModel(
            name="DeliveryMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("movement_date", models.DateField(db_index=True)),
                ("status", models.CharField(blank=True, db_index=True, max_length=120)),
                ("occurrence_text", models.CharField(blank=True, max_length=255)),
                ("attempt", models.PositiveSmallIntegerField(default=1)),
                ("weight_kg", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("volumes", models.PositiveIntegerField(default=0)),
                ("address", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="clients.clientaddress")),
                ("client", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="clients.client")),
                ("cte", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movements", to="operations.cte")),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="drivers.driver")),
                ("manifest", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movements", to="operations.manifest")),
                ("vehicle", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="drivers.vehicle")),
            ],
            options={
                "constraints":[models.UniqueConstraint(fields=("cte","manifest"), name="uniq_cte_manifest_movement")],
                "indexes":[models.Index(fields=["movement_date","driver"], name="operations__movemen_0bba38_idx"), models.Index(fields=["movement_date","client"], name="operations__movemen_df1979_idx")],
            },
        ),
        migrations.CreateModel(
            name="DeliveryOccurrence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(blank=True, db_index=True, max_length=20)),
                ("description", models.CharField(db_index=True, max_length=255)),
                ("occurred_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("source", models.CharField(default="SSW", max_length=40)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("cte", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="occurrences", to="operations.cte")),
                ("movement", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="occurrences", to="operations.deliverymovement")),
            ],
            options={"indexes":[models.Index(fields=["code","occurred_at"], name="operations__code_941cf6_idx"),models.Index(fields=["cte","occurred_at"], name="operations__cte_id_625e3d_idx"),models.Index(fields=["movement","occurred_at"], name="operations__movemen_80321e_idx")]},
        ),
    ]
