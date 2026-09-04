from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, Min, Q
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.core.models import SystemSettings
from apps.core.perf import PerfTimer
from apps.core.services import (
    calculate_driver_metrics, operational_date_map, operational_movements_for_period, parse_period,
    previous_period, with_trends,
)
from apps.operations.models import DeliveryMovement, DeliveryOccurrence
from apps.proofs.models import RetainedProof, ProofRecoverySubmission, ProofPickupOpportunity, ProofRetentionObligation
from .models import Driver, DriverPortalAccess, DriverQualityEvent
from .evaluation import coordinator_user, evaluation_v3_start_date, reopen_quality_event, review_quality_event


def _safe_post_redirect(request, fallback):
    target = (request.POST.get("next") or "").strip()
    if target and url_has_allowed_host_and_scheme(
        url=target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(fallback)


@login_required
def index(request):
    timer = PerfTimer("drivers")
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

    default_official_view = not q and not city and status == "active"
    if default_official_view:
        # Reutiliza o mesmo cache oficial do Dashboard em vez de recalcular o
        # ranking inteiro só porque a tela criou um QuerySet equivalente.
        metrics = calculate_driver_metrics(start, end)
        prev = calculate_driver_metrics(*previous_period(start, end))
    else:
        metrics = calculate_driver_metrics(
            start, end, queryset=base, include_inactive=True, include_test=(status == "test")
        )
        prev = calculate_driver_metrics(
            *previous_period(start, end), queryset=base, include_inactive=True, include_test=(status == "test")
        )
    with_trends(metrics, prev)
    timer.mark("metrics")

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
    ranking_settings = SystemSettings.load()
    podium = [m for m in metrics if m.eligible][:3]
    timer.mark("summary")
    response = render(request, "drivers/index.html", {
        "page_obj": page, "period_start": start, "period_end": end, "period_label": label, "period_mode": mode,
        "podium": podium, "ranking_settings": ranking_settings,
        "cities": cities, "q": q, "selected_city": city, "selected_status": status, "selected_sort": sort,
        "active_count": Driver.objects.filter(active=True, is_test=False).count(),
        "avg_score": avg_score, "eligible_count": len(eligible), "scored_count": len(with_activity),
        "total_weight_t": total_weight, "retained_value": retained_value, "highlights": highlights,
    })
    timer.total()
    return response


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
        path = reverse("driver_portal", args=[portal_access.token])
        public_base = (getattr(settings, "PANEL_PUBLIC_BASE_URL", "") or "").strip()
        portal_url = public_base.rstrip("/") + path if public_base else request.build_absolute_uri(path)
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


@require_POST
@login_required
def ranking_rewards_update(request):
    if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__iexact="Coordenador").exists()):
        return HttpResponseForbidden("Acesso restrito.")
    settings_obj = SystemSettings.load()
    before = {
        "top1": settings_obj.top1_reward_description,
        "top2": settings_obj.top2_reward_description,
        "top3": settings_obj.top3_reward_description,
    }
    settings_obj.top1_reward_description = (request.POST.get("top1") or "").strip()[:180]
    settings_obj.top2_reward_description = (request.POST.get("top2") or "").strip()[:180]
    settings_obj.top3_reward_description = (request.POST.get("top3") or "").strip()[:180]
    settings_obj.save(update_fields=["top1_reward_description", "top2_reward_description", "top3_reward_description", "updated_at"])
    AuditLog.objects.create(
        user=request.user, action="RANKING_REWARDS_UPDATED", entity="SystemSettings", entity_id=str(settings_obj.pk),
        before=before, after={"top1": settings_obj.top1_reward_description, "top2": settings_obj.top2_reward_description, "top3": settings_obj.top3_reward_description},
    )
    messages.success(request, "Descrições do Top 3 atualizadas. O sistema apenas exibe; a premiação continua sendo decisão da gestão.")
    return _safe_post_redirect(request, "drivers")


@login_required
def quality_reviews(request):
    timer = PerfTimer("quality.events")
    if not coordinator_user(request.user):
        return HttpResponseForbidden("Acesso restrito à coordenação.")
    # GET deve apenas consultar. Materialização de ROM13 acontece no pós-import,
    # scheduler/worker e comandos de manutenção, nunca durante a navegação.
    activation = evaluation_v3_start_date()
    qs = DriverQualityEvent.objects.filter(operation_date__gte=activation).select_related(
        "driver", "manifest", "cte", "client", "movement", "reviewed_by"
    ).order_by("-operation_date", "-pk")
    status = (request.GET.get("status") or "PENDING").strip()
    q = (request.GET.get("q") or "").strip()
    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()
    if status and status != "ALL":
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(driver__name__icontains=q) | Q(driver__cpf__icontains=q) |
            Q(manifest__number__icontains=q) | Q(cte__ctrc__icontains=q) | Q(client__name__icontains=q)
        )
    try:
        if start:
            qs = qs.filter(operation_date__gte=date.fromisoformat(start))
        if end:
            qs = qs.filter(operation_date__lte=date.fromisoformat(end))
    except ValueError:
        messages.error(request, "Período inválido.")
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    counts = {
        key: DriverQualityEvent.objects.filter(status=key, operation_date__gte=activation).count()
        for key, _ in DriverQualityEvent.Status.choices
    }
    # Omissões EXACT pertencem à Regularidade e ficam visíveis nesta mesma
    # Central para o coordenador entender o que está derrubando a nota, sem
    # transformar Ouro ignorado em obrigação.
    missed_exact = list(
        ProofPickupOpportunity.objects.filter(
            kind=ProofPickupOpportunity.Kind.EXACT, status=ProofPickupOpportunity.Status.MISSED,
            operation_date__gte=activation,
        )
        .values("driver_id", "driver__name", "proof__client_id", "proof__client__name", "operation_date")
        .annotate(
            proof_count=Count("proof_id", distinct=True),
            manifest_count=Count("manifest_id", distinct=True),
            sample_proof_id=Min("proof_id"),
        )
        .order_by("-operation_date", "driver__name")[:30]
    )
    missed_retentions = list(
        ProofRetentionObligation.objects.filter(
            status=ProofRetentionObligation.Status.MISSED, operation_date__gte=activation
        ).select_related("driver", "manifest", "proof", "proof__cte", "proof__client")
        .order_by("-operation_date", "-pk")[:30]
    )
    pending_recoveries = list(
        ProofRecoverySubmission.objects.filter(status=ProofRecoverySubmission.Status.PENDING)
        .select_related("driver", "proof", "proof__cte", "proof__client")
        .order_by("-submitted_at")[:20]
    )
    timer.total()
    return render(request, "drivers/quality_reviews.html", {
        "page_obj": page, "counts": counts, "selected_status": status, "q": q, "start": start, "end": end,
        "status_choices": DriverQualityEvent.Status.choices, "evaluation_start": activation,
        "missed_exact": missed_exact, "missed_retentions": missed_retentions,
        "pending_recoveries": pending_recoveries,
    })


@require_POST
@login_required
def quality_review_action(request, pk):
    if not coordinator_user(request.user):
        return HttpResponseForbidden("Acesso restrito à coordenação.")
    event = get_object_or_404(
        DriverQualityEvent.objects.select_related("driver", "manifest", "cte"), pk=pk
    )
    action = (request.POST.get("decision") or "").strip()
    if action == "reopen":
        reopen_quality_event(event, reviewer=request.user, note=(request.POST.get("internal_note") or "").strip())
        messages.success(request, "Avaliação reaberta. Enquanto pendente, não afeta a nota.")
    else:
        mapping = {
            "responsible": DriverQualityEvent.Status.DRIVER_RESPONSIBLE,
            "not_responsible": DriverQualityEvent.Status.NOT_RESPONSIBLE,
            "verify": DriverQualityEvent.Status.VERIFY,
        }
        status = mapping.get(action)
        if not status:
            messages.error(request, "Decisão inválida.")
            return _safe_post_redirect(request, "driver_quality_reviews")
        try:
            review_quality_event(
                event, status=status, reviewer=request.user,
                visible_reason=(request.POST.get("visible_reason") or "").strip(),
                internal_note=(request.POST.get("internal_note") or "").strip(),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return _safe_post_redirect(request, "driver_quality_reviews")
        if status == DriverQualityEvent.Status.DRIVER_RESPONSIBLE:
            messages.success(request, "Responsabilidade confirmada. A Qualidade será recalculada proporcionalmente.")
        elif status == DriverQualityEvent.Status.NOT_RESPONSIBLE:
            messages.success(request, "Ocorrência analisada como sem responsabilidade do motorista. Zero impacto.")
        else:
            messages.info(request, "Ocorrência mantida em Verificar. Zero impacto enquanto não houver decisão conclusiva.")
    return _safe_post_redirect(request, "driver_quality_reviews")
