import uuid
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name="BugReport",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("screen",models.CharField(choices=[("LOGIN","Login"),("DASHBOARD","Dashboard Executivo"),("OPERATIONS","Operação de Hoje"),("DRIVERS","Motoristas"),("DRIVER_PROFILE","Perfil do Motorista"),("PROOFS","Comprovantes Retidos"),("CLIENTS","Clientes"),("REPORTS","Relatórios"),("SSW_IMPORTS","Importações SSW"),("SSW_HISTORY","Histórico do Robô SSW"),("SETTINGS","Configurações"),("GENERAL","Geral / Navegação"),("BACKEND","Backend / Banco / Regras")],db_index=True,max_length=30)),
            ("screen_path",models.CharField(blank=True,max_length=180)), ("title",models.CharField(max_length=180)),
            ("priority",models.CharField(choices=[("P0","P0 — Bloqueador"),("P1","P1 — Crítico"),("P2","P2 — Importante"),("P3","P3 — Visual / Polimento")],db_index=True,default="P2",max_length=2)),
            ("status",models.CharField(choices=[("OPEN","Aberto"),("ANALYSIS","Em análise"),("FIXING","Em correção"),("RETEST","Aguardando reteste"),("FAILED_RETEST","Falhou no reteste"),("RESOLVED","Corrigido"),("CLOSED","Fechado")],db_index=True,default="OPEN",max_length=20)),
            ("description",models.TextField(blank=True)), ("current_result",models.TextField(blank=True)), ("expected_result",models.TextField(blank=True)), ("reproduction_steps",models.TextField(blank=True)), ("technical_notes",models.TextField(blank=True)), ("root_cause",models.TextField(blank=True)), ("resolution_notes",models.TextField(blank=True)), ("retest_notes",models.TextField(blank=True)), ("fixed_version",models.CharField(blank=True,db_index=True,max_length=30)),
            ("attachment",models.FileField(blank=True,upload_to="bug_reports/%Y/%m/",validators=[FileExtensionValidator(["png","jpg","jpeg","webp","pdf","txt","log"])])), ("app_version",models.CharField(blank=True,max_length=30)), ("browser_info",models.CharField(blank=True,max_length=250)), ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)), ("updated_at",models.DateTimeField(auto_now=True)), ("resolved_at",models.DateTimeField(blank=True,null=True)),
            ("assigned_to",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="bugs_assigned",to=settings.AUTH_USER_MODEL)), ("created_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="bugs_created",to=settings.AUTH_USER_MODEL)),
        ],options={"ordering":["-created_at"],"verbose_name":"Bug","verbose_name_plural":"Caderno de Bugs","indexes":[models.Index(fields=["screen","status"],name="bugs_bugrep_screen_829032_idx"),models.Index(fields=["priority","status"],name="bugs_bugrep_priorit_5246d2_idx")]}),
        migrations.CreateModel(name="BugExchangeReference",fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")), ("sync_id",models.UUIDField(db_index=True,default=uuid.uuid4,editable=False,unique=True)), ("created_at",models.DateTimeField(auto_now_add=True)), ("bug",models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name="exchange_reference",to="bugs.bugreport")),
        ],options={"verbose_name":"Referência de troca de bug","verbose_name_plural":"Referências de troca de bugs"}),
    ]
