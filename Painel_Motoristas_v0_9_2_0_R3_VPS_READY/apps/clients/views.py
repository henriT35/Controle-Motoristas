from collections import Counter, defaultdict
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect

from apps.core.models import SystemSettings
from apps.core.services import completed_cte_ids, operational_date_map, operational_movements_for_period, parse_period
from apps.drivers.models import Driver
from apps.operations.models import DeliveryOccurrence
from apps.proofs.models import RetainedProof
from .models import Client

ROM_SOURCE = "SSW_ROMANEIO"
OPEN_PROOF_STATUSES = [
    RetainedProof.Status.WAITING,
    RetainedProof.Status.AVAILABLE,
    RetainedProof.Status.RECOVERING,
    RetainedProof.Status.AWAITING_VALIDATION,
    RetainedProof.Status.VERIFY,
]


def _is_code(occ, code, text):
    return (str(occ.code or "").strip() == code) or (text in (occ.description or "").upper())


def _client_rows(start, end, *, q="", city="", district="", driver_id="", occurrence=""):
    movements = (
        operational_movements_for_period(start, end)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .filter(driver__is_test=False)
        .select_related("client", "address", "cte", "driver", "manifest")
    )
    if city:
        movements = movements.filter(address__city=city)
    if district:
        movements = movements.filter(address__district=district)
    if str(driver_id).isdigit():
        movements = movements.filter(driver_id=int(driver_id))
    movement_list = list(movements)
    movement_ids = {m.pk for m in movement_list}
    if occurrence and movement_ids:
        matching_ids = set(
            DeliveryOccurrence.objects.filter(movement_id__in=movement_ids, source=ROM_SOURCE)
            .filter(Q(code=occurrence) | Q(description__icontains=occurrence))
            .values_list("movement_id", flat=True)
        )
        movement_list = [m for m in movement_list if m.pk in matching_ids]
        movement_ids = matching_ids

    client_ids = {m.client_id for m in movement_list if m.client_id}
    clients = Client.objects.filter(pk__in=client_ids)
    if q:
        clients = clients.filter(Q(name__icontains=q) | Q(cnpj__icontains=q))
    allowed_client_ids = set(clients.values_list("pk", flat=True))
    movement_list = [m for m in movement_list if m.client_id in allowed_client_ids]

    cte_ids = {m.cte_id for m in movement_list}
    delivered_ids = completed_cte_ids(cte_ids, as_of=end)
    op_dates = operational_date_map(start, end)
    stats = defaultdict(lambda: {
        "attempts": 0, "ctes": set(), "delivered": set(), "drivers": set(), "cities": set(), "districts": set(),
        "weight": Decimal("0"), "last_visit": None, "retentions": 0, "time13": 0,
    })
    flags = defaultdict(lambda: {"34": False, "13": False})
    if movement_ids:
        for occ in DeliveryOccurrence.objects.filter(movement_id__in=movement_ids, source=ROM_SOURCE).only("movement_id", "code", "description"):
            if _is_code(occ, "34", "MERCADORIA EM CONFERENCIA NO CLIENTE"):
                flags[occ.movement_id]["34"] = True
            if _is_code(occ, "13", "ENTREGA PREJUDICADA PELO HORARIO"):
                flags[occ.movement_id]["13"] = True

    for m in movement_list:
        row = stats[m.client_id]
        row["attempts"] += 1
        row["ctes"].add(m.cte_id)
        if m.cte_id in delivered_ids:
            row["delivered"].add(m.cte_id)
        if m.driver_id:
            row["drivers"].add(m.driver_id)
        if m.address:
            if m.address.city: row["cities"].add(m.address.city)
            if m.address.district: row["districts"].add(m.address.district)
        row["weight"] += m.weight_kg or Decimal("0")
        op_date = op_dates.get(m.manifest_id, m.movement_date)
        if row["last_visit"] is None or op_date > row["last_visit"]:
            row["last_visit"] = op_date
        row["retentions"] += int(flags[m.pk]["34"])
        row["time13"] += int(flags[m.pk]["13"])

    proof_by_client = defaultdict(list)
    for proof in RetainedProof.objects.filter(client_id__in=allowed_client_ids, retained_at__date__lte=end).exclude(status=RetainedProof.Status.CANCELED).only(
        "client_id", "retained_at", "recovered_at", "freight_value", "status"
    ):
        proof_by_client[proof.client_id].append(proof)

    client_map = {c.pk: c for c in clients}
    rows = []
    for client_id, st in stats.items():
        client = client_map.get(client_id)
        if not client: continue
        attempts = st["attempts"]
        delivered = len(st["delivered"])
        proofs = proof_by_client.get(client_id, [])
        active = [p for p in proofs if p.retained_at.date() <= end and (not p.recovered_at or p.recovered_at.date() > end)]
        recovered = [p for p in proofs if p.recovered_at and start <= p.recovered_at.date() <= end]
        recovered_days = [(p.recovered_at.date() - p.retained_at.date()).days for p in recovered]
        rows.append({
            "client": client,
            "attempts": attempts,
            "delivered": delivered,
            "success_rate": (Decimal(delivered) / Decimal(attempts) * 100) if attempts else Decimal("0"),
            "retentions": st["retentions"],
            "retention_rate": (Decimal(st["retentions"]) / Decimal(attempts) * 100) if attempts else Decimal("0"),
            "time13": st["time13"],
            "time13_rate": (Decimal(st["time13"]) / Decimal(attempts) * 100) if attempts else Decimal("0"),
            "active_proofs": len(active),
            "retained_value": sum((p.freight_value or Decimal("0") for p in active), Decimal("0")),
            "avg_days": (sum(recovered_days) / len(recovered_days)) if recovered_days else None,
            "last_visit": st["last_visit"], "weight": st["weight"],
            "city": sorted(st["cities"])[0] if st["cities"] else "—",
            "districts": ", ".join(sorted(st["districts"])[:3]),
            "drivers": len(st["drivers"]),
        })
    return rows, movement_list


@login_required
def index(request):
    start, end, label, mode = parse_period(request, SystemSettings.load().period_default)
    q = request.GET.get("q", "").strip(); city = request.GET.get("city", "").strip(); district = request.GET.get("district", "").strip()
    driver_id = request.GET.get("driver", "").strip(); occurrence = request.GET.get("occurrence", "").strip()
    rows, period_moves = _client_rows(start, end, q=q, city=city, district=district, driver_id=driver_id, occurrence=occurrence)
    rows.sort(key=lambda r: (r["retentions"], r["attempts"]), reverse=True)
    page = Paginator(rows, 20).get_page(request.GET.get("page"))
    retained_clients = sum(1 for r in rows if r["active_proofs"])
    avg_rate = sum((r["retention_rate"] for r in rows), Decimal("0")) / Decimal(len(rows)) if rows else Decimal("0")
    retained_total = sum((r["retained_value"] for r in rows), Decimal("0"))
    top = sorted(rows, key=lambda r: r["retained_value"], reverse=True)[:8]

    # Opções geográficas vêm da base INTEIRA do período, antes dos filtros. Assim
    # Cidade -> Bairro funciona de forma dependente e não perde opções ao submeter.
    geo_moves = list(
        operational_movements_for_period(start, end)
        .filter(driver__is_test=False)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .select_related("address").only("address__city", "address__district")
    )
    city_districts = defaultdict(set)
    for movement in geo_moves:
        if not movement.address or not movement.address.city:
            continue
        if movement.address.district:
            city_districts[movement.address.city].add(movement.address.district)
    cities = sorted(city_districts.keys())
    districts = sorted(city_districts.get(city, set())) if city else sorted({d for values in city_districts.values() for d in values})
    return render(request, "clients/index.html", {
        "page_obj": page, "clients_count": len(rows), "retained_clients": retained_clients, "avg_rate": avg_rate,
        "retained_total": retained_total, "top_clients": top, "cities": cities, "districts": districts,
        "drivers": Driver.objects.filter(active=True, is_test=False).order_by("name"),
        "period_label": label, "period_start": start, "period_end": end, "period_mode": mode,
        "filters": {"q": q, "city": city, "district": district, "driver": driver_id, "occurrence": occurrence},
        "client_chart_data": [{"name": r["client"].name, "value": float(r["retained_value"])} for r in top],
        "city_districts": {name: sorted(values) for name, values in city_districts.items()},
    })


@login_required
def detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    start, end, label, mode = parse_period(request, SystemSettings.load().period_default)
    rows, moves = _client_rows(start, end, q="")
    row = next((x for x in rows if x["client"].pk == client.pk), None)
    client_moves = [m for m in moves if m.client_id == client.pk]
    driver_counts = Counter(m.driver.name for m in client_moves if m.driver)
    region_counts = Counter((m.address.city, m.address.district) for m in client_moves if m.address and m.address.city)
    proof_rows = list(
        RetainedProof.objects.filter(client=client, retained_at__date__lte=end)
        .exclude(status=RetainedProof.Status.CANCELED)
        .filter(
            Q(retained_at__date__range=(start, end))
            | Q(recovered_at__date__range=(start, end))
            | Q(recovered_at__isnull=True)
            | Q(recovered_at__date__gt=end)
        )
        .select_related("cte", "original_driver", "recovery_driver")
        .order_by("-retained_at")[:50]
    )
    for proof in proof_rows:
        retained_day = proof.retained_at.date()
        cutoff = end
        if proof.recovered_at and proof.recovered_at.date() <= end:
            cutoff = proof.recovered_at.date()
        proof.period_days_retained = max((cutoff - retained_day).days, 0)
        proof.active_at_period_end = not proof.recovered_at or proof.recovered_at.date() > end
    return render(request, "clients/detail.html", {
        "client": client, "stats": row, "movements": client_moves[:100], "proofs": proof_rows,
        "top_drivers": driver_counts.most_common(10), "top_regions": region_counts.most_common(10),
        "period_label": label, "period_start": start, "period_end": end, "period_mode": mode,
    })

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST


@require_POST
@login_required
def payment_rule(request, pk):
    if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__iexact="Coordenador").exists()):
        return HttpResponseForbidden("Acesso restrito.")
    client = get_object_or_404(Client, pk=pk)
    client.proof_required_for_payment = bool(request.POST.get("proof_required_for_payment"))
    client.proof_payment_note = (request.POST.get("proof_payment_note") or "").strip()[:255]
    client.save(update_fields=["proof_required_for_payment", "proof_payment_note"])
    messages.success(request, "Regra de comprovante do cliente atualizada.")
    return redirect("client_detail", pk=client.pk)
