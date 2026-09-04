from django.contrib import admin
from .models import RetainedProof, ProofPickupOpportunity, ProofPickupAttempt, ProofRecoverySubmission, ProofRetention, ProofRetentionObligation


@admin.register(RetainedProof)
class RetainedProofAdmin(admin.ModelAdmin):
    list_display = ("cte", "client", "original_driver", "retained_at", "status", "resolution_source", "freight_value")
    list_filter = ("status", "resolution_source", "retained_at")
    search_fields = ("cte__ctrc", "invoice_number", "client__name", "original_driver__name")


@admin.register(ProofPickupOpportunity)
class ProofPickupOpportunityAdmin(admin.ModelAdmin):
    list_display = ("operation_date", "driver", "manifest", "proof", "kind", "status", "source")
    list_filter = ("kind", "status", "source", "operation_date")
    search_fields = ("driver__name", "manifest__number", "proof__cte__ctrc", "proof__client__name")


@admin.register(ProofPickupAttempt)
class ProofPickupAttemptAdmin(admin.ModelAdmin):
    list_display = ("operation_date", "driver", "proof", "kind", "outcome", "created_at")
    list_filter = ("kind", "outcome", "operation_date")


@admin.register(ProofRecoverySubmission)
class ProofRecoverySubmissionAdmin(admin.ModelAdmin):
    list_display = ("proof", "driver", "status", "source", "submitted_at", "validated_at")
    list_filter = ("status", "source")


@admin.register(ProofRetention)
class ProofRetentionAdmin(admin.ModelAdmin):
    list_display = ("proof", "driver", "manifest", "retained_at", "created_at")


@admin.register(ProofRetentionObligation)
class ProofRetentionObligationAdmin(admin.ModelAdmin):
    list_display = ("operation_date", "driver", "manifest", "proof", "status", "fulfilled_at", "missed_at")
    list_filter = ("status", "operation_date")
    search_fields = ("driver__name", "manifest__number", "proof__cte__ctrc", "proof__client__name")
