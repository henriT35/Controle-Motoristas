from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.core.cache import versioned_key
from apps.core.models import SystemSettings
from apps.core.perf import PerfTimer
from apps.core.services import (
    calculate_driver_metrics, completed_cte_ids, operational_date_map,
    operational_movements_for_period, parse_period, previous_period,
    retention_origin_dates, with_trends,
)
from apps.operations.models import CTe, DeliveryOccurrence
from apps.drivers.models import DriverQualityEvent
from apps.drivers.evaluation import evaluation_v3_start_date
from apps.proofs.models import RetainedProof, ProofPickupOpportunity, ProofRecoverySubmission


def _basic_kpis(start, end):
    key = versioned_key("dashboard-kpis", start, end)
    cached = cache.get(key)
    if cached is not None:
        return {
            **cached,
            "proofs": RetainedProof.objects.filter(pk__in=cached["valid_proof_ids"]),
            "active_proofs_as_of": RetainedProof.objects.filter(pk__in=cached["active_ids"]),
        }

    moves = (
        operational_movements_for_period(start, end)
        .filter(driver__is_test=False)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
    )
    cte_ids = set(moves.values_list("cte_id", flat=True))
    ctes = CTe.objects.filter(pk__in=cte_ids)
    raw_proofs = list(
        RetainedProof.objects.filter(cte_id__in=cte_ids)
        .exclude(status=RetainedProof.Status.CANCELED)
        .select_related("original_manifest", "client")
    )
    origin_dates = retention_origin_dates(raw_proofs)
    valid_ids = {p.pk for p in raw_proofs if origin_dates.get(p.pk) and origin_dates[p.pk] <= end}
    active_statuses = {
        RetainedProof.Status.WAITING, RetainedProof.Status.AVAILABLE,
        RetainedProof.Status.RECOVERING, RetainedProof.Status.AWAITING_VALIDATION,
        RetainedProof.Status.VERIFY,
    }
    active_ids = {
        p.pk for p in raw_proofs
        if p.pk in valid_ids
        and p.status in active_statuses
        and (p.recovered_at is None or timezone.localtime(p.recovered_at).date() > end)
    }
    cte_totals = ctes.aggregate(total_freight=Sum("freight_value"), total_weight=Sum("weight_kg"))
    total_freight = cte_totals["total_freight"] or Decimal("0")
    total_weight = cte_totals["total_weight"] or Decimal("0")
    retained_freight = RetainedProof.objects.filter(pk__in=active_ids).aggregate(v=Sum("freight_value"))["v"] or Decimal("0")
    delivered_ids = completed_cte_ids(cte_ids, as_of=end)
    delivery_rate = Decimal(len(delivered_ids)) / Decimal(len(cte_ids)) * 100 if cte_ids else Decimal("0")
    retention_pct = retained_freight / total_freight * 100 if total_freight else Decimal("0")
    payload = {
        "cte_ids": sorted(cte_ids),
        "valid_proof_ids": sorted(valid_ids),
        "active_ids": sorted(active_ids),
        "total_freight": total_freight,
        "retained_freight": retained_freight,
        "total_weight": total_weight,
        "delivered_ids": sorted(delivered_ids),
        "delivery_rate": delivery_rate,
        "retention_pct": retention_pct,
    }
    cache.set(key, payload, timeout=300)
    return {
        **payload,
        "proofs": RetainedProof.objects.filter(pk__in=valid_ids),
        "active_proofs_as_of": RetainedProof.objects.filter(pk__in=active_ids),
    }


def _change(current, previous):
    if not previous:
        return None
    return (current - previous) / abs(previous) * Decimal("100")


def _evolution_payload(start: date, end: date):
    """Série pesada carregada separadamente e baseada na MESMA fonte temporal."""
    key = versioned_key("dashboard-evolution", start, end)
    cached = cache.get(key)
    if cached is not None:
        return cached

    moves = (
        operational_movements_for_period(start, end)
        .filter(driver__is_test=False)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
    )
    cte_ids = set(moves.values_list("cte_id", flat=True))
    day_count = (end - start).days + 1
    all_days = [start + timedelta(days=i) for i in range(day_count)]
    by_day = {day: {"entregas": 0, "retencoes": 0, "pendencias": 0} for day in all_days}
    op_dates = operational_date_map(start, end)
    activity_days = set()
    ctes_by_operational_day = defaultdict(set)
    for manifest_id, cte_id in moves.values_list("manifest_id", "cte_id"):
        op_date = op_dates.get(manifest_id)
        if op_date and start <= op_date <= end:
            activity_days.add(op_date)
            ctes_by_operational_day[op_date].add(cte_id)

    delivered_at_by_cte = {}
    delivered_rows = (
        DeliveryOccurrence.objects.filter(
            cte_id__in=cte_ids, occurred_at__isnull=False, occurred_at__date__lte=end
        )
        .filter(Q(code="1") | Q(description__icontains="ENTREGUE"))
        .exclude(description__icontains="NAO ENTREGUE")
        .values_list("cte_id", "occurred_at")
        .order_by("occurred_at")
    )
    for cte_id, occurred_at in delivered_rows:
        delivered_at_by_cte.setdefault(cte_id, timezone.localtime(occurred_at).date())
    for day, day_ctes in ctes_by_operational_day.items():
        by_day[day]["entregas"] = sum(
            1 for cte_id in day_ctes
            if delivered_at_by_cte.get(cte_id) and delivered_at_by_cte[cte_id] <= day
        )

    open_statuses = {
        RetainedProof.Status.WAITING, RetainedProof.Status.AVAILABLE,
        RetainedProof.Status.RECOVERING, RetainedProof.Status.AWAITING_VALIDATION,
        RetainedProof.Status.VERIFY,
    }
    chart_proofs = list(
        RetainedProof.objects.select_related("original_manifest")
        .exclude(status=RetainedProof.Status.CANCELED)
    )
    chart_origin_dates = retention_origin_dates(chart_proofs)
    for proof in chart_proofs:
        event_date = chart_origin_dates.get(proof.pk)
        if not event_date or not (start <= event_date <= end):
            continue
        by_day[event_date]["retencoes"] += 1
        activity_days.add(event_date)
        recovered_date = timezone.localtime(proof.recovered_at).date() if proof.recovered_at else None
        if proof.status in open_statuses or (recovered_date and recovered_date > event_date):
            by_day[event_date]["pendencias"] += 1

    days = [day for day in all_days if day.weekday() != 6 or day in activity_days]
    payload = {
        "dates": [day.isoformat() for day in days],
        "labels": [day.strftime("%d/%m") for day in days],
        "entregas": [by_day[day]["entregas"] for day in days],
        "retencoes": [by_day[day]["retencoes"] for day in days],
        "pendencias": [by_day[day]["pendencias"] for day in days],
        "detail_url": reverse("operations_today"),
    }
    cache.set(key, payload, timeout=300)
    return payload


@login_required
def evolution_data(request):
    timer = PerfTimer("dashboard.graph")
    start, end, _label, _mode = parse_period(request, SystemSettings.load().period_default)
    payload = _evolution_payload(start, end)
    timer.total()
    return JsonResponse(payload)


@login_required
def index(request):
    timer = PerfTimer("dashboard")
    start, end, period_label, period_mode = parse_period(request, SystemSettings.load().period_default)
    prev_start, prev_end = previous_period(start, end)
    # Disponibilidade já é materializada no pós-import/scheduler. Abrir o
    # Dashboard nunca dispara matching de oportunidades.
    current = _basic_kpis(start, end)
    previous_basic = _basic_kpis(prev_start, prev_end)
    timer.mark("kpis")

    active_proofs_as_of = current["active_proofs_as_of"]
    total_freight = current["total_freight"]
    retained_freight = current["retained_freight"]
    total_weight = current["total_weight"]
    delivery_rate = current["delivery_rate"]
    retention_pct = current["retention_pct"]
    proofs = current["proofs"]
    trends = {
        "freight": _change(total_freight, previous_basic["total_freight"]),
        "retained_freight": _change(retained_freight, previous_basic["retained_freight"]),
        "weight": _change(total_weight, previous_basic["total_weight"]),
        "delivery_pp": delivery_rate - previous_basic["delivery_rate"],
        "retention_pp": retention_pct - previous_basic["retention_pct"],
    }

    metrics = with_trends(calculate_driver_metrics(start, end), calculate_driver_metrics(prev_start, prev_end))
    top_drivers = [m for m in metrics if m.eligible][:5]
    timer.mark("ranking")

    settings_obj = SystemSettings.load()
    critical_threshold = end - timedelta(days=int(settings_obj.critical_days or 15))
    waiting = active_proofs_as_of.count()
    active_list = list(active_proofs_as_of.select_related("original_manifest"))
    active_origin_dates = retention_origin_dates(active_list)
    critical = sum(1 for p in active_list if active_origin_dates.get(p.pk) and active_origin_dates[p.pk] < critical_threshold)
    recovered = proofs.filter(recovered_at__date__range=(start, end)).count()
    available = RetainedProof.objects.filter(status=RetainedProof.Status.AVAILABLE).count()
    priority_clients = list(
        active_proofs_as_of.values("client__name")
        .annotate(count=Count("id"), value=Sum("freight_value"))
        .order_by("-count")[:4]
    )
    timer.mark("proofs")

    # Pendências de governança da Nota V3 / comprovantes. São consultas simples
    # e indexadas; não disparam reconstrução histórica pesada.
    evaluation_start = evaluation_v3_start_date()
    quality_pending = DriverQualityEvent.objects.filter(
        status=DriverQualityEvent.Status.PENDING, operation_date__gte=evaluation_start
    ).count()
    exact_missed = (
        ProofPickupOpportunity.objects.filter(
            kind=ProofPickupOpportunity.Kind.EXACT, status=ProofPickupOpportunity.Status.MISSED
        )
        .values("driver_id", "proof__client_id", "operation_date")
        .distinct()
        .count()
    )
    recovery_pending = ProofRecoverySubmission.objects.filter(status=ProofRecoverySubmission.Status.PENDING).count()
    tracking_ssw = RetainedProof.objects.filter(status=RetainedProof.Status.TRACKING).count()
    quality_reopened = DriverQualityEvent.objects.filter(
        reopened_count__gt=0, status=DriverQualityEvent.Status.PENDING, operation_date__gte=evaluation_start
    ).count()
    auto_resolved_recent = RetainedProof.objects.filter(
        status=RetainedProof.Status.RECOVERED, resolution_source="SSW",
        updated_at__date__gte=timezone.localdate() - timedelta(days=6),
    ).count()

    params = request.GET.urlencode()
    evolution_url = reverse("dashboard_evolution") + (f"?{params}" if params else "")
    context = {
        "period_start": start, "period_end": end, "period_label": period_label, "period_mode": period_mode,
        "total_freight": total_freight, "retained_freight": retained_freight, "retention_pct": retention_pct,
        "total_weight_t": total_weight / Decimal("1000"), "retained_count": waiting,
        "delivery_rate": delivery_rate, "top_drivers": top_drivers,
        "waiting_count": waiting, "available_count": available, "recovered_count": recovered, "critical_count": critical,
        "priority_clients": priority_clients, "released_freight": max(total_freight - retained_freight, Decimal("0")),
        "dashboard_chart_data": {"retention": float(retention_pct), "evolution": None, "evolution_url": evolution_url},
        "trends": trends,
        "quality_pending_count": quality_pending, "exact_missed_count": exact_missed,
        "recovery_pending_count": recovery_pending, "tracking_ssw_count": tracking_ssw,
        "quality_reopened_count": quality_reopened, "auto_resolved_recent_count": auto_resolved_recent,
    }
    timer.total()
    return render(request, "dashboard/index.html", context)
