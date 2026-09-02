from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import render
from django.utils import timezone

from apps.core.models import SystemSettings
from apps.core.services import (
    calculate_driver_metrics, completed_cte_ids, operational_date_map,
    operational_movements_for_period, parse_period, previous_period,
    retention_origin_dates, with_trends,
)
from apps.operations.models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof
from apps.operations.services import refresh_today_opportunities


def _basic_kpis(start, end):
    moves = operational_movements_for_period(start, end).filter(driver__is_test=False).exclude(status__iexact="CANCELADO").exclude(manifest__status__iexact="CANCELADO")
    cte_ids = set(moves.values_list("cte_id", flat=True))
    ctes = CTe.objects.filter(pk__in=cte_ids)

    # A fotografia histórica dos comprovantes usa a origem temporal de domínio
    # (ROM34 / rota canônica), nunca retained_at/importação isoladamente.
    raw_proofs = list(
        RetainedProof.objects.filter(cte_id__in=cte_ids)
        .exclude(status=RetainedProof.Status.CANCELED)
        .select_related("original_manifest", "client")
    )
    origin_dates = retention_origin_dates(raw_proofs)
    valid_ids = {p.pk for p in raw_proofs if origin_dates.get(p.pk) and origin_dates[p.pk] <= end}
    proofs = RetainedProof.objects.filter(pk__in=valid_ids).exclude(status=RetainedProof.Status.CANCELED)
    active_ids = {
        p.pk for p in raw_proofs
        if p.pk in valid_ids and (p.recovered_at is None or timezone.localtime(p.recovered_at).date() > end)
    }
    active_as_of = RetainedProof.objects.filter(pk__in=active_ids)

    cte_totals = ctes.aggregate(total_freight=Sum("freight_value"), total_weight=Sum("weight_kg"))
    total_freight = cte_totals["total_freight"] or Decimal("0")
    total_weight = cte_totals["total_weight"] or Decimal("0")
    retained_freight = active_as_of.aggregate(v=Sum("freight_value"))["v"] or Decimal("0")
    delivered_ids = completed_cte_ids(cte_ids, as_of=end)
    delivery_rate = Decimal(len(delivered_ids)) / Decimal(len(cte_ids)) * 100 if cte_ids else Decimal("0")
    retention_pct = retained_freight / total_freight * 100 if total_freight else Decimal("0")
    return {
        "moves": moves, "cte_ids": cte_ids, "ctes": ctes, "proofs": proofs,
        "active_proofs_as_of": active_as_of, "origin_dates": origin_dates,
        "total_freight": total_freight, "retained_freight": retained_freight,
        "total_weight": total_weight, "delivered_ids": delivered_ids,
        "delivery_rate": delivery_rate, "retention_pct": retention_pct,
    }


def _change(current, previous):
    if not previous:
        return None
    return (current - previous) / abs(previous) * Decimal("100")


@login_required
def index(request):
    start, end, period_label, period_mode = parse_period(request, SystemSettings.load().period_default)
    prev_start, prev_end = previous_period(start, end)
    available_today_ids = refresh_today_opportunities()
    current = _basic_kpis(start, end)
    previous_basic = _basic_kpis(prev_start, prev_end)
    moves=current["moves"]; cte_ids=current["cte_ids"]; ctes=current["ctes"]; proofs=current["proofs"]
    active_proofs_as_of = current["active_proofs_as_of"]
    total_freight=current["total_freight"]; retained_freight=current["retained_freight"]; total_weight=current["total_weight"]
    delivered_ids=current["delivered_ids"]; delivery_rate=current["delivery_rate"]; retention_pct=current["retention_pct"]
    trends={
        "freight": _change(total_freight, previous_basic["total_freight"]),
        "retained_freight": _change(retained_freight, previous_basic["retained_freight"]),
        "weight": _change(total_weight, previous_basic["total_weight"]),
        "delivery_pp": delivery_rate - previous_basic["delivery_rate"],
        "retention_pp": retention_pct - previous_basic["retention_pct"],
    }

    metrics = calculate_driver_metrics(start, end)
    previous = calculate_driver_metrics(prev_start, prev_end)
    metrics = with_trends(metrics, previous)
    top_drivers = [m for m in metrics if m.eligible][:5]

    # Série histórica por EVENTO operacional. Domingo vazio é omitido apenas da
    # visualização; domingo com qualquer movimentação continua aparecendo.
    day_count = (end - start).days + 1
    all_days = [start + timedelta(days=i) for i in range(day_count)]
    by_day = {day: {"entregas": 0, "retencoes": 0, "pendencias": 0} for day in all_days}

    op_dates = operational_date_map(start, end)
    activity_days = set()
    ctes_by_operational_day = defaultdict(set)
    for movement in moves.only("manifest_id", "cte_id"):
        op_date = op_dates.get(movement.manifest_id)
        if op_date and start <= op_date <= end:
            activity_days.add(op_date)
            ctes_by_operational_day[op_date].add(movement.cte_id)

    # Entregas do gráfico usam a mesma DATA OPERACIONAL da tentativa/romaneio.
    # O evento ENTREGUE apenas determina se aquele CT-e já estava concluído até
    # o fechamento do seu dia operacional; sua data posterior não migra a rota
    # para outro ponto do gráfico. Assim o clique do Dashboard reconcilia com a
    # Operação do Dia.
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

    open_proof_statuses = {
        RetainedProof.Status.WAITING, RetainedProof.Status.AVAILABLE,
        RetainedProof.Status.RECOVERING, RetainedProof.Status.AWAITING_VALIDATION,
    }
    # Retenção/Pendência entram no ponto do gráfico apenas na DATA DE ORIGEM.
    # Uma atualização posterior do CT-e nunca migra o evento para outro dia.
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
        if proof.status in open_proof_statuses or (recovered_date and recovered_date > event_date):
            by_day[event_date]["pendencias"] += 1

    days = [
        day for day in all_days
        if day.weekday() != 6 or day in activity_days
    ]
    evolution = {
        "dates": [day.isoformat() for day in days],
        "labels": [day.strftime("%d/%m") for day in days],
        "entregas": [by_day[day]["entregas"] for day in days],
        "retencoes": [by_day[day]["retencoes"] for day in days],
        "pendencias": [by_day[day]["pendencias"] for day in days],
        "detail_url": "/operacao/hoje/",
    }

    settings = SystemSettings.load()
    # KPIs temporais: reconstruídos pela data real da retenção/recuperação. O
    # status atual não pode reescrever a fotografia de um período histórico.
    critical_threshold = end - timedelta(days=int(settings.critical_days or 15))
    waiting = active_proofs_as_of.count()
    active_list = list(active_proofs_as_of.select_related("original_manifest"))
    active_origin_dates = retention_origin_dates(active_list)
    critical = sum(1 for p in active_list if active_origin_dates.get(p.pk) and active_origin_dates[p.pk] < critical_threshold)
    recovered = proofs.filter(recovered_at__date__range=(start, end)).count()
    # "Disponíveis hoje" é um indicador operacional do dia atual e não deve ficar
    # preso ao período histórico selecionado no dashboard. Inclui retenções antigas
    # que podem ser recuperadas por uma rota ativa hoje.
    available = RetainedProof.objects.filter(
        pk__in=available_today_ids, status=RetainedProof.Status.AVAILABLE
    ).count()
    priority_clients = list(
        active_proofs_as_of.values("client__name")
        .annotate(count=Count("id"), value=Sum("freight_value"))
        .order_by("-count")[:4]
    )

    return render(request, "dashboard/index.html", {
        "period_start":start, "period_end":end, "period_label":period_label, "period_mode":period_mode,
        "total_freight":total_freight, "retained_freight":retained_freight, "retention_pct":retention_pct,
        "total_weight_t":total_weight/Decimal("1000"), "retained_count":waiting,
        "delivery_rate":delivery_rate, "top_drivers":top_drivers, "evolution":evolution,
        "waiting_count":waiting, "available_count":available, "recovered_count":recovered, "critical_count":critical,
        "priority_clients":priority_clients, "released_freight":max(total_freight-retained_freight, Decimal("0")),
        "dashboard_chart_data": {"retention": float(retention_pct), "evolution": evolution}, "trends": trends,
    })
