from django.contrib import admin

from .models import BugReport


@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "screen", "priority", "status", "created_by", "created_at")
    list_filter = ("screen", "priority", "status")
    search_fields = ("title", "description", "current_result", "expected_result")
    autocomplete_fields = ("created_by", "assigned_to")
