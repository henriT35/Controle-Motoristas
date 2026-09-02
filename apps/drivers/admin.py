from django.contrib import admin
from .models import Driver, Vehicle


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
