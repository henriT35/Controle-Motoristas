from django.conf import settings
from django.db import models


class GeneratedReport(models.Model):
    class Format(models.TextChoices):
        HTML="HTML","HTML"
        XLSX="XLSX","Excel"
        PDF="PDF","PDF"
    report_type=models.CharField(max_length=40,db_index=True)
    start_date=models.DateField()
    end_date=models.DateField()
    format=models.CharField(max_length=10,choices=Format.choices)
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    status=models.CharField(max_length=20,default="SUCCESS",db_index=True)
    file_name=models.CharField(max_length=255,blank=True)
    duration_ms=models.PositiveIntegerField(default=0)
    row_count=models.PositiveIntegerField(default=0)
    file_size=models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering=["-created_at"]
        indexes=[models.Index(fields=["report_type", "start_date", "end_date", "format"], name="reports_gen_report__7f56d9_idx")]
