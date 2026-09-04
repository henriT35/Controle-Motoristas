from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clients", "0001_initial"),
        ("operations", "0001_initial"),
        ("drivers", "0002_v0_9_1_0_portal_access_requests"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriverQualityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(db_index=True, default="13", max_length=20)),
                ("operation_date", models.DateField(db_index=True)),
                ("status", models.CharField(choices=[
                    ("PENDING", "Pendente de validação"),
                    ("DRIVER_RESPONSIBLE", "Responsabilidade do motorista"),
                    ("NOT_RESPONSIBLE", "Não foi responsabilidade do motorista"),
                    ("VERIFY", "Não foi possível determinar"),
                ], db_index=True, default="PENDING", max_length=24)),
                ("visible_reason", models.TextField(blank=True)),
                ("internal_note", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("reopened_count", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("client", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="driver_quality_events", to="clients.client")),
                ("cte", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="driver_quality_events", to="operations.cte")),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_events", to="drivers.driver")),
                ("manifest", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="driver_quality_events", to="operations.manifest")),
                ("movement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quality_events", to="operations.deliverymovement")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="driver_quality_events_reviewed", to=settings.AUTH_USER_MODEL)),
                ("source_occurrence", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="quality_review_events", to="operations.deliveryoccurrence")),
            ],
            options={"ordering": ["-operation_date", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="driverqualityevent",
            constraint=models.UniqueConstraint(fields=("movement", "code"), name="uniq_quality_event_movement_code"),
        ),
        migrations.AddIndex(
            model_name="driverqualityevent",
            index=models.Index(fields=["status", "operation_date"], name="drivers_qe_status_date_idx"),
        ),
        migrations.AddIndex(
            model_name="driverqualityevent",
            index=models.Index(fields=["driver", "operation_date"], name="drivers_qe_driver_date_idx"),
        ),
        migrations.CreateModel(
            name="DriverScoreSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("score_date", models.DateField(db_index=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("general_score", models.DecimalField(decimal_places=2, max_digits=5)),
                ("proof_management_score", models.DecimalField(decimal_places=2, max_digits=5)),
                ("operational_quality_score", models.DecimalField(decimal_places=2, max_digits=5)),
                ("regularity_score", models.DecimalField(decimal_places=2, max_digits=5)),
                ("recovery_bonus", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("eligible", models.BooleanField(default=False)),
                ("breakdown", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="score_snapshots", to="drivers.driver")),
            ],
            options={"ordering": ["-score_date", "-updated_at"]},
        ),
        migrations.AddConstraint(
            model_name="driverscoresnapshot",
            constraint=models.UniqueConstraint(fields=("driver", "score_date", "period_start", "period_end"), name="uniq_driver_score_snapshot_period"),
        ),
        migrations.AddIndex(
            model_name="driverscoresnapshot",
            index=models.Index(fields=["driver", "score_date"], name="drivers_score_driver_date_idx"),
        ),
    ]
