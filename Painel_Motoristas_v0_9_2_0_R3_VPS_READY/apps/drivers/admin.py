from django.contrib import admin
from .models import Driver, Vehicle, DriverQualityEvent, DriverScoreSnapshot


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("name", "cpf", "active", "is_test", "updated_at")
    list_filter = ("active", "is_test")
    search_fields = ("name", "cpf")
    list_editable = ("active", "is_test")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate", "description", "active")
    list_filter = ("active",)
    search_fields = ("plate", "description")


@admin.register(DriverQualityEvent)
class DriverQualityEventAdmin(admin.ModelAdmin):
    list_display = ("operation_date", "driver", "manifest", "cte", "code", "status", "reviewed_by", "reviewed_at")
    list_filter = ("status", "code", "operation_date")
    search_fields = ("driver__name", "driver__cpf", "manifest__number", "cte__ctrc", "visible_reason")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DriverScoreSnapshot)
class DriverScoreSnapshotAdmin(admin.ModelAdmin):
    list_display = ("score_date", "driver", "general_score", "proof_management_score", "operational_quality_score", "regularity_score", "recovery_bonus", "attempts", "eligible")
    list_filter = ("score_date", "eligible")
    search_fields = ("driver__name", "driver__cpf")
    readonly_fields = tuple(field.name for field in DriverScoreSnapshot._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
