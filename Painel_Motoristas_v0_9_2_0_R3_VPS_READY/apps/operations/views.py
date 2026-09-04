from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.perf import PerfTimer
from apps.core.services import (
    completed_cte_ids,
    latest_operational_date,
    manifests_for_operational_date,
    operational_date_for_manifest,
    operational_manifest_classification_map,
    operational_manifest_evidence_map,
    operational_date_map,
    operational_movements_for_period,
    parse_period,
    planned_manifests,
    retention_origin_dates,
    retention_stats_for_date,
)
from .models import CTe, DeliveryMovement, DeliveryOccurrence, Manifest
from .services import build_manifest_cards, find_pickup_opportunities, opportunities_summary
from .geo import METRICS, active_branch, cached_geo_summary
from .geodata_loader import neighborhood_feature_collection


def normalize_status(value):
    return (value or "").strip().upper()


@login_required
def today(request):
    timer = PerfTimer("operation.today")
    try:
        d = date.fromisoformat(request.GET.get("date")) if request.GET.get("date") else timezone.localdate()
    except (TypeError, ValueError):
        d = timezone.localdate()

    manifests = list(
        manifests_for_operational_date(d)
        .filter(driver__is_test=False)
        .exclude(status__iexact="CANCELADO")
        .select_related("driver", "vehicle")
        .order_by("driver__name", "number")
    )
    cards = build_manifest_cards(
        manifests,
        # A disponibilidade é materializada no pós-import/scheduler; GET não
        # grava estado derivado nem força matching global do estoque.
        persist_available=False,
        operational_date=d,
    )
    timer.mark("cards")
    classifications = operational_manifest_classification_map(d)
    all_evidence = operational_manifest_evidence_map(d, d)
    for card in cards:
        manifest_id = card["manifest"].pk
        card["route_confidence"] = classifications.get(manifest_id, "CARRYOVER" if d == timezone.localdate() else "INFERRED")
        card["canonical_date"] = all_evidence.get(manifest_id, {}).get("date")
    planning_manifests = []
    planning_cards = []
    if d >= timezone.localdate():
        planning_manifests = list(
            planned_manifests(timezone.localdate())
            .filter(driver__is_test=False)
            .select_related("driver", "vehicle")
            .order_by("driver__name", "number")
        )
        planning_cards = build_manifest_cards(
            planning_manifests, persist_available=False, operational_date=d
        ) if planning_manifests else []
        for card in planning_cards:
            card["route_confidence"] = "PLANNED"
    moves = [m for card in cards for m in card.get("move_objects", ()) if normalize_status(m.status) != "CANCELADO"]
    delivered_count = sum(card["delivered"] for card in cards)
    clients_count = len({m.client_id for m in moves if m.client_id})
    total_weight = sum((m.weight_kg or Decimal("0") for m in moves), Decimal("0"))

    exact_ids, regional_ids = opportunities_summary(cards)
    retention_stats = retention_stats_for_date(d)

    latest_date = latest_operational_date()
    timer.mark("summary")
    response = render(
        request,
        "operations/today.html",
        {
            "selected_date": d,
            "latest_date": latest_date,
            "cards": cards,
            "planning_cards": planning_cards,
            "drivers_in_route": len({m.driver_id for m in manifests}),
            "movements_count": len(moves),
            "delivered_count": delivered_count,
            "clients_count": clients_count,
            "total_weight_t": total_weight / Decimal("1000"),
            "exact_opportunities": len(exact_ids),
            "regional_opportunities": len(regional_ids),
            "retained_today": retention_stats["retained"],
            "retained_recovered_later": retention_stats["recovered_later"],
            "retained_still_open": retention_stats["still_open"],
            "robot_unit": active_branch(),
            "is_today": d == timezone.localdate(),
            "is_future": d > timezone.localdate(),
            "is_past": d < timezone.localdate(),
            "previous_date": d - timedelta(days=1),
            # Histórico sempre pode avançar até hoje. A partir de hoje, liberamos
            # amanhã somente quando existem romaneios recentes ainda em planejamento.
            # Isso permite enxergar preparação sem afirmar que ela pertence ao dia futuro.
            "next_date": (
                d + timedelta(days=1)
                if d < timezone.localdate() or (d == timezone.localdate() and bool(planning_cards))
                else None
            ),
            "focus": request.GET.get("focus", ""),
        },
    )
    timer.total()
    return response


def _safe_next_url(request, fallback_name="deliveries"):
    candidate = (request.GET.get("next") or request.POST.get("next") or "").strip()
    if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return candidate
    return reverse(fallback_name)


@login_required
def manifest_detail(request, pk):
    manifest = get_object_or_404(
        Manifest.objects.select_related("driver", "vehicle"), pk=pk
    )
    preferred_date = None
    if request.GET.get("date"):
        try:
            preferred_date = date.fromisoformat(request.GET["date"])
        except ValueError:
            pass
    route_date = operational_date_for_manifest(manifest, preferred_date)
    exact, regional = find_pickup_opportunities(manifest, as_of=route_date)
    moves = manifest.movements.select_related("cte", "client", "address").order_by(
        "client__name"
    )
    delivered_ids = completed_cte_ids(set(moves.values_list("cte_id", flat=True)), as_of=route_date)
    classification = operational_manifest_classification_map(route_date).get(manifest.pk, "PLANNED")
    return render(
        request,
        "operations/manifest_detail.html",
        {
            "manifest": manifest,
            "route_date": route_date,
            "route_confidence": classification,
            "movements": moves,
            "delivered_ids": delivered_ids,
            "exact": exact,
            "regional": regional,
            "return_url": _safe_next_url(request, "operations_today") if request.GET.get("next") else f"{reverse('operations_today')}?date={route_date.isoformat()}",
        },
    )


@login_required
def cte_detail(request, pk):
    cte = get_object_or_404(CTe.objects.select_related("client"), pk=pk)
    movements = list(
        cte.movements.select_related(
            "manifest", "manifest__driver", "manifest__vehicle", "driver", "client", "address"
        ).order_by("manifest__date", "attempt", "pk")
    )
    evidence = operational_manifest_evidence_map()
    for movement in movements:
        item = evidence.get(movement.manifest_id)
        movement.operational_date_display = item["date"] if item else None
        movement.route_confidence_display = item["confidence"] if item else "PLANNED"

    occurrences = list(
        cte.occurrences.select_related("movement", "movement__manifest")
        .order_by("-occurred_at", "-imported_at", "-pk")
    )
    current_ctrc = next((o for o in occurrences if o.source == "SSW_CTRC"), None)
    proof = None
    submissions = []
    try:
        proof = cte.retained_proof
    except Exception:
        proof = None
    if proof:
        submissions = list(
            proof.recovery_submissions.select_related("driver", "submitted_by", "validated_by").all()[:20]
        )
        origin = retention_origin_dates([proof]).get(proof.pk)
    else:
        origin = None

    return render(request, "operations/cte_detail.html", {
        "cte": cte,
        "movements": movements,
        "occurrences": occurrences,
        "current_ctrc": current_ctrc,
        "proof": proof,
        "proof_origin_date": origin,
        "submissions": submissions,
        "attempt_count": len(movements),
        "return_url": _safe_next_url(request),
    })


@login_required
def deliveries(request):
    start, end, period_label, period_mode = parse_period(request, "30d")
    qs = (
        operational_movements_for_period(start, end)
        .filter(driver__is_test=False)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .select_related("cte", "cte__retained_proof", "client", "address", "driver", "manifest", "manifest__vehicle")
    )

    q = (request.GET.get("q") or "").strip()
    driver_id = (request.GET.get("driver") or "").strip()
    client_q = (request.GET.get("client") or "").strip()
    manifest_q = (request.GET.get("manifest") or "").strip()
    city = (request.GET.get("city") or "").strip()
    district = (request.GET.get("district") or "").strip()
    occurrence = (request.GET.get("occurrence") or "").strip()
    delivery = (request.GET.get("delivery") or "").strip()
    attempt_filter = (request.GET.get("attempt") or "").strip()
    retention = (request.GET.get("retention") or "").strip()
    proof_status = (request.GET.get("proof_status") or "").strip()
    order = (request.GET.get("order") or "date_desc").strip()

    if q:
        qs = qs.filter(
            Q(cte__ctrc__icontains=q) | Q(cte__invoice_number__icontains=q)
            | Q(client__name__icontains=q) | Q(manifest__number__icontains=q)
        )
    if driver_id.isdigit():
        qs = qs.filter(driver_id=int(driver_id))
    if client_q:
        qs = qs.filter(client__name__icontains=client_q)
    if manifest_q:
        qs = qs.filter(manifest__number__icontains=manifest_q)
    if city:
        qs = qs.filter(address__city=city)
    if district:
        qs = qs.filter(address__district=district)
    if occurrence:
        qs = qs.filter(
            Q(occurrences__description__icontains=occurrence)
            | Q(occurrences__code__iexact=occurrence)
        ).distinct()
    if retention == "yes":
        qs = qs.filter(cte__retained_proof__isnull=False)
    elif retention == "no":
        qs = qs.filter(cte__retained_proof__isnull=True)
    if proof_status:
        qs = qs.filter(cte__retained_proof__status=proof_status)

    if attempt_filter in {"first", "reentry"}:
        attempt_rows = DeliveryMovement.objects.values("cte_id").annotate(n=Count("id"))
        if attempt_filter == "first":
            ids = attempt_rows.filter(n=1).values_list("cte_id", flat=True)
        else:
            ids = attempt_rows.filter(n__gt=1).values_list("cte_id", flat=True)
        qs = qs.filter(cte_id__in=ids)

    all_cte_ids = set(qs.values_list("cte_id", flat=True))
    delivered_ids = completed_cte_ids(all_cte_ids, as_of=end)
    if delivery == "delivered":
        qs = qs.filter(cte_id__in=delivered_ids)
    elif delivery == "pending":
        qs = qs.exclude(cte_id__in=delivered_ids)

    # KPIs reconciliáveis com exatamente o conjunto filtrado.
    filtered_cte_ids = set(qs.values_list("cte_id", flat=True))
    # ``delivered_ids`` já foi calculado para o conjunto-base com o mesmo corte
    # temporal. Intersectar evita repetir toda a consulta de ocorrências ENTREGUE.
    delivered_filtered = delivered_ids.intersection(filtered_cte_ids)
    totals = qs.aggregate(weight=Sum("weight_kg"), volumes=Sum("volumes"))
    retained_ctes = qs.filter(cte__retained_proof__isnull=False).values("cte_id").distinct().count()

    movement_rows = list(qs)
    op_dates = operational_date_map(start, end)
    evidence = operational_manifest_evidence_map(start, end)
    attempt_counts = dict(
        DeliveryMovement.objects.filter(cte_id__in={m.cte_id for m in movement_rows})
        .values_list("cte_id").annotate(n=Count("id"))
    )
    for movement in movement_rows:
        movement.operational_date_display = op_dates.get(movement.manifest_id)
        item = evidence.get(movement.manifest_id)
        movement.route_confidence_display = item["confidence"] if item else (
            "CARRYOVER" if movement.operational_date_display else "PLANNED"
        )
        movement.delivered_display = movement.cte_id in delivered_filtered
        movement.attempt_count_display = attempt_counts.get(movement.cte_id, 1)

    # Ordenação por data significa data OPERACIONAL, não emissão do romaneio.
    # Como a data canônica é domínio calculado, a ordenação final é feita após
    # resolver a evidência temporal, antes da paginação.
    if order == "date_asc":
        movement_rows.sort(key=lambda m: (m.operational_date_display or date.min, m.pk))
    elif order == "client":
        movement_rows.sort(key=lambda m: ((getattr(m.client, "name", "") or "").upper(), -(m.operational_date_display or date.min).toordinal(), m.pk))
    elif order == "driver":
        movement_rows.sort(key=lambda m: ((getattr(m.driver, "name", "") or "").upper(), -(m.operational_date_display or date.min).toordinal(), m.pk))
    elif order == "cte":
        movement_rows.sort(key=lambda m: ((getattr(m.cte, "ctrc", "") or "").upper(), m.pk))
    else:
        movement_rows.sort(key=lambda m: (m.operational_date_display or date.min, m.pk), reverse=True)

    page_obj = Paginator(movement_rows, 50).get_page(request.GET.get("page"))

    from apps.drivers.models import Driver
    from apps.proofs.models import RetainedProof
    drivers = Driver.objects.filter(active=True, is_test=False).order_by("name")
    cities = list(
        DeliveryMovement.objects.exclude(address__city="").values_list("address__city", flat=True).distinct().order_by("address__city")
    )
    districts_qs = DeliveryMovement.objects.exclude(address__district="")
    if city:
        districts_qs = districts_qs.filter(address__city=city)
    districts = list(districts_qs.values_list("address__district", flat=True).distinct().order_by("address__district"))

    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    return render(request, "operations/deliveries.html", {
        "page_obj": page_obj,
        "period_start": start, "period_end": end, "period_label": period_label, "period_mode": period_mode,
        "drivers": drivers, "cities": cities, "districts": districts,
        "proof_statuses": RetainedProof.Status.choices,
        "query_without_page": query_without_page.urlencode(),
        "total_attempts": len(movement_rows),
        "total_ctes": len(filtered_cte_ids),
        "total_delivered": len(delivered_filtered),
        "total_retained": retained_ctes,
        "total_weight_t": (totals["weight"] or Decimal("0")) / Decimal("1000"),
        "total_volumes": totals["volumes"] or 0,
        "active_branch": active_branch(),
    })


def _parse_geo_date(raw, fallback):
    try:
        return date.fromisoformat(raw) if raw else fallback
    except (TypeError, ValueError):
        return fallback


@login_required
def map_operational(request):
    today_date = timezone.localdate()
    start = _parse_geo_date(request.GET.get("start"), today_date)
    end = _parse_geo_date(request.GET.get("end"), start)
    if start > end:
        start, end = end, start
    from apps.drivers.models import Driver
    return render(
        request,
        "operations/map.html",
        {
            "selected_start": start,
            "selected_end": end,
            "active_branch": active_branch(),
            "geo_metrics": METRICS.values(),
            "drivers": Driver.objects.filter(active=True, is_test=False).order_by("name"),
        },
    )


@login_required
def geo_summary_api(request):
    today_date = timezone.localdate()
    start = _parse_geo_date(request.GET.get("start") or request.GET.get("date"), today_date)
    end = _parse_geo_date(request.GET.get("end"), start)
    if start > end:
        start, end = end, start
    metric = request.GET.get("metric", "delivered")
    level = request.GET.get("level", "auto")
    parent_state = request.GET.get("parent_state", "")
    parent_city = request.GET.get("parent_city", "")
    branch = request.GET.get("branch") or active_branch()
    driver_id = request.GET.get("driver") or None
    try:
        driver_id = int(driver_id) if driver_id else None
    except (TypeError, ValueError):
        return JsonResponse({"error": "Motorista inválido."}, status=400)
    try:
        payload = cached_geo_summary(
            start, end, branch=branch, metric=metric, level=level,
            parent_state=parent_state, parent_city=parent_city, driver_id=driver_id,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})


@login_required
def geo_neighborhood_geometry_api(request):
    state = (request.GET.get("state") or "").strip()
    city = (request.GET.get("city") or "").strip()
    districts = [x.strip() for x in (request.GET.get("districts") or "").split("|") if x.strip()]
    if not state or not city or not districts:
        return JsonResponse({"error": "Informe UF, município e bairros."}, status=400)
    force_retry = request.GET.get("retry") in {"1", "true", "yes"}
    collection, meta = neighborhood_feature_collection(state, city, districts, force_retry=force_retry)
    response = JsonResponse(collection, json_dumps_params={"ensure_ascii": False})
    response["X-Geo-Resolved"] = str(len(meta["resolved"]))
    response["X-Geo-Unresolved"] = str(len(meta["unresolved"]))
    return response


@login_required
def geo_diagnostics_api(request):
    from .geodata_loader import neighborhood_feature_collection
    state = (request.GET.get("state") or "PA").strip()
    city = (request.GET.get("city") or "").strip()
    districts = [x.strip() for x in (request.GET.get("districts") or "").split("|") if x.strip()]
    if not city:
        return JsonResponse({"error": "Município obrigatório."}, status=400)
    _, meta = neighborhood_feature_collection(state, city, districts, allow_network=False)
    return JsonResponse(meta, json_dumps_params={"ensure_ascii": False})
