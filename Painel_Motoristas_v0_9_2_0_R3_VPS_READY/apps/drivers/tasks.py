from celery import shared_task
from django.utils import timezone

from apps.core.warmup import warm_navigation_cache

from .evaluation import (
    ensure_actions_activation_date, finalize_expired_pickup_opportunities, materialize_exact_pickup_opportunities,
    sync_quality_events_for_movements, sync_retention_obligations,
)


@shared_task
def evaluation_housekeeping():
    """Persistência diária da avaliação V3.

    Fecha EXACT sem manifestação como MISSED, expira GOLD de forma neutra e
    garante que ROM13 importados existam como eventos pendentes. Idempotente.
    """
    activation = ensure_actions_activation_date()
    created = sync_quality_events_for_movements()
    retention = sync_retention_obligations()
    exact_history = materialize_exact_pickup_opportunities(start=activation, end=timezone.localdate())
    finalized = finalize_expired_pickup_opportunities()
    warmed = warm_navigation_cache()
    snapshots = warmed.get("snapshots_current", 0)
    return {
        "actions_activation_date": activation.isoformat(),
        "quality_created": created,
        "retention_obligations": retention,
        "exact_history": exact_history,
        "score_snapshots": snapshots,
        "cache_warmup": warmed,
        **finalized,
    }
