from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial=True
    dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name="GeneratedReport", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("report_type",models.CharField(db_index=True,max_length=40)), ("start_date",models.DateField()), ("end_date",models.DateField()),
        ("format",models.CharField(choices=[("HTML","HTML"),("XLSX","Excel"),("PDF","PDF")],max_length=10)),
        ("created_at",models.DateTimeField(auto_now_add=True,db_index=True)), ("status",models.CharField(db_index=True,default="SUCCESS",max_length=20)),
        ("file_name",models.CharField(blank=True,max_length=255)), ("duration_ms",models.PositiveIntegerField(default=0)), ("row_count",models.PositiveIntegerField(default=0)), ("file_size",models.PositiveBigIntegerField(default=0)),
        ("requested_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL)),
    ], options={"ordering":["-created_at"],"indexes":[models.Index(fields=["report_type","start_date","end_date","format"],name="reports_gen_report__7f56d9_idx")]})]
