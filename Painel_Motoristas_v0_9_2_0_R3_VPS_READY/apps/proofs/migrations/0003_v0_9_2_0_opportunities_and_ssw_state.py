from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("drivers", "0003_v0_9_2_0_quality_events"),
        ("operations", "0001_initial"),
        ("proofs", "0002_v0_9_1_0_portal_proofs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="retainedproof",
            name="status",
            field=models.CharField(choices=[
                ("AGUARDANDO_RETIRADA", "Aguardando retirada"),
                ("DISPONIVEL_HOJE", "Disponível hoje"),
                ("EM_RECUPERACAO", "Em recuperação"),
                ("AGUARDANDO_VALIDACAO", "Aguardando validação"),
                ("VERIFICAR", "Verificar"),
                ("ACOMPANHANDO_SSW", "Acompanhando SSW"),
                ("RECUPERADO", "Recuperado"),
                ("CANCELADO", "Cancelado"),
            ], db_index=True, default="AGUARDANDO_RETIRADA", max_length=30),
        ),
        migrations.AddField(model_name="retainedproof", name="resolution_source", field=models.CharField(blank=True, db_index=True, max_length=30)),
        migrations.AddField(model_name="retainedproof", name="last_ssw_code", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="retainedproof", name="last_ssw_description", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="retainedproof", name="last_ssw_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name="ProofRetentionObligation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_date", models.DateField(db_index=True)),
                ("status", models.CharField(choices=[("PENDING", "Aguardando encerramento"), ("FULFILLED", "Ressalva registrada"), ("MISSED", "Sem ressalva registrada")], db_index=True, default="PENDING", max_length=16)),
                ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
                ("missed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="proof_retention_obligations", to="drivers.driver")),
                ("manifest", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="proof_retention_obligations", to="operations.manifest")),
                ("movement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="proof_retention_obligations", to="operations.deliverymovement")),
                ("proof", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="retention_obligations", to="proofs.retainedproof")),
            ],
            options={"ordering": ["-operation_date", "-pk"]},
        ),
        migrations.AddConstraint(
            model_name="proofretentionobligation",
            constraint=models.UniqueConstraint(fields=("proof", "movement"), name="uniq_retention_obligation_attempt"),
        ),
        migrations.AddIndex(
            model_name="proofretentionobligation",
            index=models.Index(fields=["driver", "operation_date", "status"], name="proofs_retobl_driver_date_idx"),
        ),
        migrations.AddIndex(
            model_name="proofretentionobligation",
            index=models.Index(fields=["status", "operation_date"], name="proofs_retobl_status_date_idx"),
        ),
        migrations.CreateModel(
            name="ProofPickupOpportunity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_date", models.DateField(db_index=True)),
                ("kind", models.CharField(choices=[("EXACT", "Retirada exata"), ("GOLD", "Oportunidade de ouro")], db_index=True, max_length=10)),
                ("status", models.CharField(choices=[
                    ("PRESENTED", "Apresentada"),
                    ("RESPONDED", "Respondida"),
                    ("MISSED", "Sem manifestação"),
                    ("EXPIRED_NEUTRAL", "Encerrada sem impacto"),
                    ("CLOSED", "Encerrada"),
                ], db_index=True, default="PRESENTED", max_length=20)),
                ("source", models.CharField(choices=[("PORTAL", "Portal do motorista"), ("WHATSAPP", "WhatsApp"), ("SYSTEM", "Sistema")], default="PORTAL", max_length=20)),
                ("first_presented_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("last_presented_at", models.DateTimeField(auto_now=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("outcome", models.CharField(blank=True, max_length=20)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("driver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="proof_pickup_opportunities", to="drivers.driver")),
                ("manifest", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="proof_pickup_opportunities", to="operations.manifest")),
                ("proof", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pickup_opportunities", to="proofs.retainedproof")),
            ],
            options={"ordering": ["-operation_date", "-first_presented_at"]},
        ),
        migrations.AddConstraint(
            model_name="proofpickupopportunity",
            constraint=models.UniqueConstraint(fields=("proof", "driver", "manifest", "operation_date", "kind"), name="uniq_pickup_opportunity_day"),
        ),
        migrations.AddIndex(
            model_name="proofpickupopportunity",
            index=models.Index(fields=["driver", "operation_date", "kind"], name="proofs_opp_drv_date_kind_idx"),
        ),
        migrations.AddIndex(
            model_name="proofpickupopportunity",
            index=models.Index(fields=["status", "operation_date"], name="proofs_opp_status_date_idx"),
        ),
    ]
