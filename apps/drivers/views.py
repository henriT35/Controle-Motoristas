from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.models import SystemSettings
from apps.core.services import (
    calculate_driver_metrics, operational_date_map, operational_movements_for_period, parse_period,
    previous_period, with_trends,
)
from apps.operations.models import DeliveryMovement, DeliveryOccurrence
from apps.proofs.models import RetainedProof, ProofRecoverySubmission
from .models import Driver, DriverPortalAccess


@login_required
def index(request):
    start, end, label, mode = parse_period(request, SystemSettings.load().period_default)
    q = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()
    status = request.GET.get("status", "active")

    # Por padrão, homologação/fictícios ficam fora de toda análise oficial.
    # Administradores ainda conseguem encontrá-los escolhendo o filtro Testes.
    base = Driver.objects.all()
    if q:
        base = base.filter(Q(name__icontains=q) | Q(cpf__icontains=q))
    if status == "test":
        base = base.filter(is_test=True)
    else:
        base = base.filter(is_test=False)
        if status == "active":
            base = base.filter(active=True)
        elif status == "inactive":
            base = base.filter(active=False)

    if city:
        driver_ids = operational_movements_for_period(start, end).filter(
            address__city=city, driver__is_test=False
        ).values_list("driver_id", flat=True)
        base = base.filter(pk__in=driver_ids).distinct()

    metrics = calculate_driver_metrics(start, end, queryset=base, include_inactive=True, include_test=(status == "test"))
    prev = calculate_driver_metrics(*previous_period(start, end), queryset=base, include_inactive=True, include_test=(status == "test"))
    with_trends(metrics, prev)

    sort = request.GET.get("sort", "score")
    if sort == "movements":
        metrics.sort(key=lambda m: (m.movements, m.performance_score), reverse=True)
    elif sort == "weight":
        metrics.sort(key=lambda m: (m.weight_kg, m.movements), reverse=True)
    elif sort == "retained":
        metrics.sort(key=lambda m: (m.retention_rate, m.movements), reverse=True)
    elif sort == "productivity":
        metrics.sort(key=lambda m: (m.productivity_score, m.movements), reverse=True)
    elif sort == "recoveries":
        metrics.sort(key=lambda m: (m.recovered, m.movements), reverse=True)
    else:
        # Ranking de desempenho SEMPRE prioriza amostra elegível. Isso impede
        # 5/5 de aparecer acima de centenas de tentativas consistentes.
        metrics.sort(key=lambda m: (m.eligible, m.ranking_score, m.performance_score, m.movements), reverse=True)

    paginator = Paginator(metrics, 20)
    page = paginator.get_page(request.GET.get("page"))
    cities = (
        operational_movements_for_period(start, end)
        .filter(driver__is_test=False)
        .exclude(address__city="")
        .values_list("address__city", flat=True).distinct().order_by("address__city")
    )
    eligible = [m for m in metrics if m.eligible]
    with_activity = [m for m in metrics if m.movements > 0]
    # A média não deve virar 0 apenas porque ninguém alcançou ainda o corte do
    # ranking. Elegibilidade continua separada e visível para não mascarar amostra.
    avg_score = (
        sum((m.performance_score for m in with_activity), Decimal("0")) / Decimal(len(with_activity))
        if with_activity else Decimal("0")
    )
    total_weight = sum((m.weight_kg for m in metrics), Decimal("0")) / Decimal("1000")
    retained_value = sum((m.retained_value for m in metrics), Decimal("0"))
    highlights = {
        "volume": max(metrics, key=lambda m: m.weight_kg, default=None),
        "score": max(eligible, key=lambda m: (m.ranking_score, m.performance_score, m.movements), default=None),
        "recoveries": max(metrics, key=lambda m: (m.recovered, m.movements), default=None),
        "retained": max(metrics, key=lambda m: (m.retention_rate, m.movements), default=None),
    }
    return render(request, "drivers/index.html", {
        "page_obj": page, "period_start": start, "period_end": end, "period_label": label, "period_mode": mode,
        "cities": cities, "q": q, "selected_city": city, "selected_status": status, "selected_sort": sort,
        "active_count": Driver.objects.filter(active=True, is_test=False).count(),
        "avg_score": avg_score, "eligible_count": len(eligible), "scored_count": len(with_activity),
        "total_weight_t": total_weight, "retained_value": retained_value, "highlights": highlights,
    })


@login_required
def detail(request, pk):
    driver=get_object_or_404(Driver,pk=pk)
    start,end,label,mode=parse_period(request, SystemSettings.load().period_default)
    metric_list=calculate_driver_metrics(start,end,queryset=Driver.objects.filter(pk=driver.pk),include_inactive=True,include_test=True)
    metric=metric_list[0] if metric_list else None
    period_moves = operational_movements_for_period(start,end).filter(driver=driver).exclude(status__iexact="CANCELADO").exclude(manifest__status__iexact="CANCELADO")
    moves=list(period_moves.select_related("cte","client","manifest","address").order_by("-movement_date")[:100])
    period_move_ids = period_moves.values_list("pk", flat=True)
    occ=(DeliveryOccurrence.objects.filter(movement_id__in=period_move_ids).values_list("description",flat=True))
    occurrence_counts=Counter(x or "Sem descrição" for x in occ)
    client_counts=Counter(m.client.name for m in moves if m.client)
    monthly_labels=[]; monthly_mov=[]
    cursor=date(end.year,end.month,1)
    months=[]
    for _ in range(12):
        months.append(cursor)
        cursor=(cursor.replace(day=1)-timedelta(days=1)).replace(day=1)
    months=list(reversed(months))
    twelve_start=months[0]
    twelve_moves=list(
        operational_movements_for_period(twelve_start,end)
        .filter(driver=driver)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .only("id","manifest_id","movement_date")
    )
    twelve_dates=operational_date_map(twelve_start,end)
    monthly_counts=Counter()
    for movement in twelve_moves:
        op_date=twelve_dates.get(movement.manifest_id,movement.movement_date)
        monthly_counts[(op_date.year,op_date.month)] += 1
    for month in months:
        monthly_labels.append(month.strftime("%m/%y"))
        monthly_mov.append(monthly_counts[(month.year,month.month)])
    cities_served = sorted({m.address.city for m in moves if m.address and m.address.city})
    insights=[]
    district_counts = Counter(
        (m.address.city, m.address.district) for m in moves
        if m.address and m.address.city and m.address.district
    )
    recoveries = list(
        RetainedProof.objects.filter(recovery_driver=driver, recovered_at__date__range=(start, end), status=RetainedProof.Status.RECOVERED)
        .select_related("cte", "client", "original_driver").order_by("-recovered_at")[:20]
    )
    active_proofs = list(
        RetainedProof.objects.filter(original_driver=driver, retained_at__date__lte=end)
        .filter(Q(recovered_at__isnull=True) | Q(recovered_at__date__gt=end))
        .exclude(status=RetainedProof.Status.CANCELED)
        .select_related("cte", "client").order_by("retained_at")[:20]
    )
    # A tabela histórica precisa mostrar a idade NO FECHAMENTO selecionado. A
    # propriedade model.days_retained é deliberadamente atual e seria incorreta
    # ao consultar agosto em setembro.
    for proof in active_proofs:
        proof.period_days_retained = max((end - timezone.localtime(proof.retained_at).date()).days, 0)
    portal_access = DriverPortalAccess.objects.filter(driver=driver).first()
    portal_url = None
    if portal_access and portal_access.active and (request.user.is_staff or request.user.is_superuser):
        from django.urls import reverse
        portal_url = request.build_absolute_uri(reverse("driver_portal", args=[portal_access.token]))
    if metric:
        insights.append(f"Taxa de sucesso de {metric.success_rate:.1f}% em {metric.movements} tentativas no período.")
        if metric.retained:
            insights.append(f"{metric.retained} retenções ({metric.retention_rate:.1f}%) foram atribuídas às tentativas deste motorista.")
        if metric.time_window_failures:
            insights.append(f"{metric.time_window_failures} eventos por horário ({metric.time_window_rate:.1f}%) no período.")
        if metric.active_proofs:
            insights.append(f"{metric.active_proofs} comprovantes permaneciam ativos no fechamento; o mais antigo tinha {metric.max_proof_days} dias.")
        if metric.recovered:
            insights.append(f"{metric.recovered} comprovantes foram resgatados por este motorista no período.")
        if client_counts:
            top3=sum(v for _,v in client_counts.most_common(3)); share=Decimal(top3)/Decimal(len(moves))*100 if moves else 0
            insights.append(f"Os 3 clientes mais atendidos concentram {share:.1f}% das movimentações do período.")
    return render(request,"drivers/detail.html",{
        "driver":driver,"metric":metric,"movements":moves,"period_start":start,"period_end":end,"period_label":label,"period_mode":mode,
        "occurrence_labels":[x for x,_ in occurrence_counts.most_common(8)],"occurrence_values":[v for _,v in occurrence_counts.most_common(8)],
        "client_labels":[x for x,_ in client_counts.most_common(6)],"client_values":[v for _,v in client_counts.most_common(6)],
        "monthly_labels":monthly_labels,"monthly_movements":monthly_mov,"insights":insights,"cities_served":cities_served,
        "district_rows":[{"city": city, "district": district, "attempts": count} for (city,district),count in district_counts.most_common(12)],
        "recoveries": recoveries, "active_proofs": active_proofs, "portal_access": portal_access, "portal_url": portal_url,
        "can_manage_portal": request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__iexact="Coordenador").exists(),
    })


@require_POST
@login_required
def toggle_test(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Acesso restrito.")
    driver = get_object_or_404(Driver, pk=pk)
    before = {"is_test": driver.is_test}
    driver.is_test = not driver.is_test
    driver.save(update_fields=["is_test", "updated_at"])
    AuditLog.objects.create(
        user=request.user, action="DRIVER_TEST_FLAG_CHANGED", entity="Driver", entity_id=str(driver.pk),
        before=before, after={"is_test": driver.is_test},
    )
    if driver.is_test:
        messages.success(request, "Motorista marcado como teste/homologação e removido dos indicadores oficiais.")
    else:
        messages.success(request, "Motorista voltou a participar dos indicadores oficiais.")
    return redirect("driver_detail", pk=driver.pk)
