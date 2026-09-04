from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[("drivers","0002_v0_9_1_0_portal_access_requests"),("operations","0001_initial"),("proofs","0001_initial")]
    operations=[
        migrations.CreateModel(
            name="ProofRetention",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("retained_at",models.DateTimeField(db_index=True)),
                ("evidence",models.FileField(blank=True,upload_to="proof_retention/%Y/%m/")),
                ("note",models.TextField(blank=True)),
                ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("driver",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="proof_retentions_reported",to="drivers.driver")),
                ("manifest",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to="operations.manifest")),
                ("proof",models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name="retention_evidence",to="proofs.retainedproof")),
            ],
            options={"indexes":[models.Index(fields=["driver","retained_at"],name="proofs_proo_driver__05b467_idx")]},
        ),
        migrations.CreateModel(
            name="ProofPickupAttempt",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("operation_date",models.DateField(db_index=True)),
                ("kind",models.CharField(choices=[("EXACT","Retirada exata"),("GOLD","Oportunidade de ouro")],db_index=True,max_length=10)),
                ("outcome",models.CharField(choices=[("RECOVERED","Retirei"),("NOT_RELEASED","Ainda não liberado"),("UNABLE","Não foi possível tentar")],db_index=True,max_length=20)),
                ("note",models.TextField(blank=True)),
                ("evidence",models.FileField(blank=True,upload_to="proof_attempts/%Y/%m/")),
                ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("driver",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="proof_pickup_attempts",to="drivers.driver")),
                ("manifest",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="proof_pickup_attempts",to="operations.manifest")),
                ("proof",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="pickup_attempts",to="proofs.retainedproof")),
                ("submission",models.OneToOneField(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="pickup_attempt",to="proofs.proofrecoverysubmission")),
            ],
            options={
                "ordering":["-created_at"],
                "constraints":[models.UniqueConstraint(fields=("proof","driver","manifest","operation_date","kind"),name="uniq_pickup_attempt_offer_day")],
                "indexes":[models.Index(fields=["driver","operation_date","kind"],name="proofs_proo_driver__077d69_idx"),models.Index(fields=["proof","outcome"],name="proofs_proo_proof_i_d8cc8e_idx")],
            },
        ),
    ]
