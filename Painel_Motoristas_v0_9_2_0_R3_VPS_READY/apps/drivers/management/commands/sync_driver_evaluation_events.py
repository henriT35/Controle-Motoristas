from django.core.management.base import BaseCommand
from apps.core.warmup import warm_navigation_cache
from apps.drivers.evaluation import (
    ensure_actions_activation_date, finalize_expired_pickup_opportunities, materialize_exact_pickup_opportunities,
    sync_quality_events_for_movements, sync_retention_obligations,
)


class Command(BaseCommand):
    help = "Materializa ROM13 pendentes e finaliza oportunidades antigas de forma idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true")
        parser.add_argument("--skip-warmup", action="store_true", help="Não aquece cache ao final; útil quando o startup fará um único warmup consolidado.")

    def handle(self, *args, **options):
        activation = ensure_actions_activation_date()
        created = sync_quality_events_for_movements()
        retention = sync_retention_obligations()
        exact_history = materialize_exact_pickup_opportunities(start=activation)
        finalized = finalize_expired_pickup_opportunities()
        if options.get("skip_warmup"):
            warmed = {}
            snapshots = 0
        else:
            warmed = warm_navigation_cache()
            snapshots = warmed.get("snapshots_current", 0)
        if not options["quiet"]:
            self.stdout.write(self.style.SUCCESS(
                f"Ativação ações: {activation}; ROM13 novos: {created}; "
                f"obrigações de retenção: {retention}; histórico exato: {exact_history}; oportunidades finalizadas: {finalized}; "
                f"snapshots: {snapshots}; cache: {warmed}"
            ))
