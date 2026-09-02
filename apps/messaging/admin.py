from django.contrib import admin
from .models import WhatsAppMessage


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ("driver", "operation_date", "kind", "status", "phone", "created_at", "sent_at")
    list_filter = ("status", "kind", "operation_date")
    search_fields = ("driver__name", "phone", "body", "manifest__number")
