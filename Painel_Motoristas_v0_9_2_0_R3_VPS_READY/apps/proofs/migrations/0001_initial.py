from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL),("clients","0001_initial"),("drivers","0001_initial"),("operations","0001_initial")]
    operations=[
        migrations.CreateModel(
            name="RetainedProof",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice_number", models.CharField(blank=True, max_length=80)),
                ("retained_at", models.DateTimeField(db_index=True)),
                ("freight_value", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("merchandise_value", models.DecimalField(decimal_places=2, default=0, max_digits=16)),
                ("weight_kg", models.DecimalField(decimal_places=3, default=0, max_digits=14)),
                ("volumes", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("AGUARDANDO_RETIRADA","Aguardando retirada"),("DISPONIVEL_HOJE","Disponível hoje"),("EM_RECUPERACAO","Em recuperação"),("AGUARDANDO_VALIDACAO","Aguardando validação"),("VERIFICAR","Verificar"),("RECUPERADO","Recuperado"),("CANCELADO","Cancelado")], db_index=True, default="AGUARDANDO_RETIRADA", max_length=30)),
                ("recovered_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("address", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="clients.clientaddress")),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="retained_proofs", to="clients.client")),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("cte", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="retained_proof", to="operations.cte")),
                ("original_driver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="originated_retained_proofs", to="drivers.driver")),
                ("original_manifest", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="operations.manifest")),
                ("recovery_driver", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recovered_proofs", to="drivers.driver")),
            ],
            options={"indexes":[models.Index(fields=["status","retained_at"], name="proofs_reta_status_9c7988_idx"),models.Index(fields=["client","status"], name="proofs_reta_client__1567c0_idx"),models.Index(fields=["original_driver","retained_at"], name="proofs_reta_origina_855a85_idx")]},
        ),
        migrations.CreateModel(
            name="ProofRecoverySubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("recovered_at", models.DateTimeField()),
                ("status", models.CharField(choices=[("PENDING","Aguardando validação"),("APPROVED","Aprovada"),("REJECTED","Rejeitada")], db_index=True, default="PENDING", max_length=20)),
                ("source", models.CharField(choices=[("COORDINATOR","Coordenador"),("DRIVER_PORTAL","Portal do motorista")], default="COORDINATOR", max_length=20)),
                ("evidence", models.FileField(blank=True, upload_to="proof_recovery/%Y/%m/")),
                ("note", models.TextField(blank=True)),
                ("submitted_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                ("validation_note", models.TextField(blank=True)),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="proof_recovery_submissions", to="drivers.driver")),
                ("proof", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recovery_submissions", to="proofs.retainedproof")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="proof_recovery_submissions_created", to=settings.AUTH_USER_MODEL)),
                ("validated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="proof_recovery_submissions_validated", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-submitted_at"],"indexes":[models.Index(fields=["status","submitted_at"], name="proofs_proo_status_aeb59b_idx"),models.Index(fields=["driver","recovered_at"], name="proofs_proo_driver__bc6882_idx")]},
        ),
    ]
