from django.contrib import admin
from .models import RetainedProof

@admin.register(RetainedProof)
class RetainedProofAdmin(admin.ModelAdmin):
    list_display = ("cte", "client", "original_driver", "retained_at", "status", "freight_value")
    list_filter = ("status", "retained_at")
    search_fields = ("cte__ctrc", "invoice_number", "client__name", "original_driver__name")
