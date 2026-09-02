from django.contrib import admin
from .models import SystemSettings

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "critical_days", "minimum_sample", "sync_frequency_hours", "updated_at")
