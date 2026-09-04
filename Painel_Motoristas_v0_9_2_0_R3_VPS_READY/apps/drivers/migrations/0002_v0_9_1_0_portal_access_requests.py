from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL),("drivers","0001_initial")]
    operations=[
        migrations.CreateModel(
            name="DriverPortalAccessRequest",
            fields=[
                ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("requested_phone",models.CharField(blank=True,max_length=20)),
                ("reason",models.CharField(blank=True,max_length=255)),
                ("status",models.CharField(choices=[("PENDING","Pendente"),("APPROVED","Aprovada"),("REJECTED","Rejeitada")],db_index=True,default="PENDING",max_length=16)),
                ("requested_at",models.DateTimeField(auto_now_add=True,db_index=True)),
                ("reviewed_at",models.DateTimeField(blank=True,null=True)),
                ("review_note",models.CharField(blank=True,max_length=255)),
                ("sent_via_whatsapp",models.BooleanField(default=False)),
                ("driver",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="portal_access_requests",to="drivers.driver")),
                ("generated_access",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="approved_requests",to="drivers.driverportalaccess")),
                ("reviewed_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="driver_portal_access_requests_reviewed",to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["-requested_at"],"indexes":[models.Index(fields=["status","requested_at"],name="drivers_dri_status_e3c5d8_idx"),models.Index(fields=["driver","status"],name="drivers_dri_driver__4f7925_idx")]},
        )
    ]
