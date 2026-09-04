from django.core.management.base import BaseCommand

from apps.core.warmup import warm_navigation_cache


class Command(BaseCommand):
    help = "Pré-aquece cache compartilhado das telas críticas sem iniciar o servidor web."

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true")

    def handle(self, *args, **options):
        result = warm_navigation_cache()
        if not options["quiet"]:
            self.stdout.write(self.style.SUCCESS(
                "Cache preparado: " + ", ".join(f"{k}={v}" for k, v in result.items())
            ))
