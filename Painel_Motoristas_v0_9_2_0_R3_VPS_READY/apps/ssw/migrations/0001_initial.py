from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="ImportRun",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("kind",models.CharField(choices=[("FAST","Atualização rápida"),("MONTH","Reconciliação mensal"),("HISTORY","Importação histórica"),("MANUAL","Manual")],max_length=20)),
            ("start_date",models.DateField(db_index=True)), ("end_date",models.DateField(db_index=True)),
            ("status",models.CharField(choices=[("QUEUED","Na fila"),("DISPATCHED","Enviado ao robô"),("RUNNING","Em andamento"),("SUCCESS","Sucesso"),("WARNING","Aviso"),("ERROR","Erro")],db_index=True,default="QUEUED",max_length=20)),
            ("started_at",models.DateTimeField(blank=True,null=True)), ("finished_at",models.DateTimeField(blank=True,null=True)), ("source_file",models.CharField(blank=True,max_length=255)),
            ("new_count",models.PositiveIntegerField(default=0)), ("updated_count",models.PositiveIntegerField(default=0)), ("unchanged_count",models.PositiveIntegerField(default=0)), ("ignored_count",models.PositiveIntegerField(default=0)), ("error_count",models.PositiveIntegerField(default=0)), ("message",models.TextField(blank=True)),
            ("parse_seconds",models.FloatField(db_default=0,default=0)), ("normalize_seconds",models.FloatField(db_default=0,default=0)), ("preload_seconds",models.FloatField(db_default=0,default=0)), ("compare_seconds",models.FloatField(db_default=0,default=0)), ("database_seconds",models.FloatField(db_default=0,default=0)), ("postprocess_seconds",models.FloatField(db_default=0,default=0)), ("total_seconds",models.FloatField(db_default=0,default=0)),
            ("rows_read",models.PositiveIntegerField(db_default=0,default=0)), ("rows_valid",models.PositiveIntegerField(db_default=0,default=0)),
            ("created_at",models.DateTimeField(auto_now_add=True)),
            ("requested_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
        ],options={"indexes":[models.Index(fields=["status","created_at"],name="ssw_importr_status_140239_idx"),models.Index(fields=["kind","start_date","end_date"],name="ssw_importr_kind_816ee4_idx")]}),
        migrations.CreateModel(name="ImportStep",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")), ("name",models.CharField(max_length=80)), ("status",models.CharField(default="PENDING",max_length=20)), ("occurred_at",models.DateTimeField(blank=True,null=True)), ("message",models.TextField(blank=True)),
            ("run",models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name="steps",to="ssw.importrun")),
        ]),
    ]
