import datetime
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="SystemSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period_default", models.CharField(default="month", max_length=20)),
                ("timezone_name", models.CharField(default="America/Belem", max_length=64)),
                ("currency", models.CharField(default="BRL", max_length=8)),
                ("decimal_places", models.PositiveSmallIntegerField(default=2)),
                ("sync_frequency_hours", models.PositiveSmallIntegerField(default=3)),
                ("recent_window_days", models.PositiveSmallIntegerField(default=15)),
                ("monthly_reconcile_time", models.TimeField(default=datetime.time(23, 0))),
                ("log_retention_days", models.PositiveIntegerField(default=90)),
                ("critical_days", models.PositiveSmallIntegerField(default=15)),
                ("alert_min_days", models.PositiveSmallIntegerField(default=7)),
                ("minimum_sample", models.PositiveIntegerField(default=20)),
                ("proof_sla_days", models.PositiveSmallIntegerField(default=7)),
                ("driver_score_delivery_weight", models.DecimalField(decimal_places=2, default=35, max_digits=5)),
                ("driver_score_clean_weight", models.DecimalField(decimal_places=2, default=20, max_digits=5)),
                ("driver_score_retention_weight", models.DecimalField(decimal_places=2, default=20, max_digits=5)),
                ("driver_score_time_window_weight", models.DecimalField(decimal_places=2, default=15, max_digits=5)),
                ("driver_score_proof_weight", models.DecimalField(decimal_places=2, default=10, max_digits=5)),
                ("driver_score_recovery_weight", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("driver_rank_min_attempts", models.PositiveIntegerField(default=30)),
                ("operational_weight", models.DecimalField(decimal_places=2, default=60, max_digits=5)),
                ("effort_weight", models.DecimalField(decimal_places=2, default=40, max_digits=5)),
                ("effort_movements_weight", models.DecimalField(decimal_places=2, default=35, max_digits=5)),
                ("effort_stops_weight", models.DecimalField(decimal_places=2, default=25, max_digits=5)),
                ("effort_manifests_weight", models.DecimalField(decimal_places=2, default=20, max_digits=5)),
                ("effort_weight_kg_weight", models.DecimalField(decimal_places=2, default=20, max_digits=5)),
                ("theme", models.CharField(default="dark", max_length=20)),
                ("accent", models.CharField(default="blue", max_length=20)),
                ("density", models.CharField(default="comfortable", max_length=20)),
                ("notification_emails", models.TextField(blank=True)),
                ("email_notifications_enabled", models.BooleanField(default=False)),
                ("daily_summary_enabled", models.BooleanField(default=False)),
                ("daily_summary_time", models.TimeField(default=datetime.time(8, 0))),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name":"Configuração do sistema","verbose_name_plural":"Configurações do sistema"},
        ),
    ]
