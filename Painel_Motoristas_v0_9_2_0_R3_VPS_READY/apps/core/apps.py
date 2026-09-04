from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        # Registro explícito da invalidação centralizada de cache operacional.
        from . import signals  # noqa: F401
