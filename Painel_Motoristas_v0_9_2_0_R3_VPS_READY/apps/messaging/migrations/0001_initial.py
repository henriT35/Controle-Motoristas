from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL),("drivers","0001_initial"),("operations","0001_initial")]
    operations=[migrations.CreateModel(name="WhatsAppMessage",fields=[
        ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")), ("operation_date",models.DateField(db_index=True)), ("phone",models.CharField(max_length=20)), ("portal_url",models.TextField(blank=True)), ("body",models.TextField()),
        ("kind",models.CharField(choices=[("DAILY","Operação do dia"),("MANIFEST","Manifesto/Romaneio"),("MANUAL","Manual")],db_index=True,default="DAILY",max_length=20)),
        ("status",models.CharField(choices=[("PENDING","Pendente"),("SENDING","Enviando"),("SENT","Enviado"),("FAILED","Falhou"),("CANCELED","Cancelado")],db_index=True,default="PENDING",max_length=20)),
        ("error",models.TextField(blank=True)), ("attempt_count",models.PositiveSmallIntegerField(default=0)), ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)), ("started_at",models.DateTimeField(blank=True,null=True)), ("sent_at",models.DateTimeField(blank=True,db_index=True,null=True)),
        ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="whatsapp_messages_created",to=settings.AUTH_USER_MODEL)),
        ("driver",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="whatsapp_messages",to="drivers.driver")),
        ("manifest",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="whatsapp_messages",to="operations.manifest")),
    ],options={"ordering":["-created_at"],"indexes":[models.Index(fields=["status","created_at"],name="messaging_w_status_36a147_idx"),models.Index(fields=["operation_date","driver"],name="messaging_w_operati_7db751_idx")]})]
