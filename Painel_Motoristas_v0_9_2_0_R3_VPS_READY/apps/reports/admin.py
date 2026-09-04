from django.contrib import admin
from .models import GeneratedReport

@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ("report_type", "start_date", "end_date", "format", "requested_by", "created_at", "status")
    list_filter = ("report_type", "format", "status")
