from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.models import AuditLog
from apps.core.models import SystemSettings
from apps.core.perf import PerfTimer
from apps.core.services import calculate_driver_metrics, manifests_for_operational_date, planned_manifests
from apps.core.performance import build_performance_v3_score, percent
from apps.operations.models import DeliveryMovement
from apps.operations.services import build_manifest_cards, opportunities_summary
from apps.proofs.models import ProofPickupAttempt, ProofPickupOpportunity, ProofRecoverySubmission, ProofRetention, RetainedProof
from .evaluation import evaluation_events_for_driver, mark_opportunity_responded, present_pickup_opportunities, score_history_for_driver, snapshot_driver_scores, sync_retention_obligations
from .models import Driver, DriverPortalAccess, DriverPortalAccessRequest

MAX_EVIDENCE_BYTES = 12 * 1024 * 1024
ALLOWED_EVIDENCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
OPEN_PROOF_STATUSES = {
    RetainedProof.Status.WAITING,
    RetainedProof.Status.AVAILABLE,
    RetainedProof.Status.RECOVERING,
}


def _staff(user):
    return user.is_authenticated and (
        user.is_staff or user.is_superuser or user.groups.filter(name__iexact="Coordenador").exists()
    )


def _portal_access(token: str):
    access = DriverPortalAccess.objects.select_related("driver").filter(token=token, active=True).first()
    if access:
        access.last_used_at = timezone.now()
        access.save(update_fields=["last_used_at"])
    return access


def _portal_or_404(token: str) -> DriverPortalAccess:
    access = _portal_access(token)
    if not access:
        raise Http404("Acesso do motorista inválido ou revogado.")
    return access


def _validate_evidence(upload, *, required=False):
    if not upload:
        return "Envie uma foto ou PDF como evidência." if required else None
    ext = Path(upload.name).suffix.lower()
    if ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        return "Use JPG, PNG, WEBP ou PDF."
    if upload.size > MAX_EVIDENCE_BYTES:
        return "A evidência deve ter no máximo 12 MB."
    return None


def _request_evidence(request):
    """Aceita o campo V3 e os dois campos legados câmera/arquivo.

    A compatibilidade evita quebrar links/formulários antigos e preserva a UX
    móvel que oferece captura por câmera separada do seletor de arquivo/PDF.
    """
    return (
        request.FILES.get("evidence")
        or request.FILES.get("evidence_camera")
        or request.FILES.get("evidence_file")
    )


def _driver_opportunities(driver: Driver, target_date=None):
    target_date = target_date or timezone.localdate()
    manifests = list(
        manifests_for_operational_date(target_date)
        .filter(driver=driver)
        .exclude(status__iexact="CANCELADO")
        .select_related("driver", "vehicle")
        .order_by("number")
    )
    cards = build_manifest_cards(manifests, persist_available=False, operational_date=target_date)
    exact_ids, regional_ids = opportunities_summary(cards)
    manifest_by_proof_id = {}
    for card in cards:
        for opportunity in card.get("exact", []):
            manifest_by_proof_id.setdefault(opportunity.proof.pk, card["manifest"])
        for opportunity in card.get("regional", []):
            manifest_by_proof_id.setdefault(opportunity.proof.pk, card["manifest"])
    proof_ids = set(exact_ids) | set(regional_ids)
    proofs = list(
        RetainedProof.objects.filter(pk__in=proof_ids, status__in=OPEN_PROOF_STATUSES)
        .select_related("cte", "client", "address", "original_driver", "original_manifest")
        .order_by("-retained_at")
    )
    kind_by_id = {pk: ProofPickupAttempt.Kind.EXACT for pk in exact_ids}
    for pk in regional_ids:
        kind_by_id.setdefault(pk, ProofPickupAttempt.Kind.GOLD)
    for proof in proofs:
        proof.opportunity_kind = kind_by_id.get(proof.pk, ProofPickupAttempt.Kind.GOLD)
        proof.route_manifest = manifest_by_proof_id.get(proof.pk)
    # A oportunidade só entra na Regularidade quando foi efetivamente apresentada
    # neste Portal/ação. GOLD é persistida apenas para histórico e nunca penaliza.
    present_pickup_opportunities(
        driver=driver, proofs=proofs, kind_by_id=kind_by_id,
        manifest_by_proof_id=manifest_by_proof_id, operation_date=target_date,
        source=ProofPickupOpportunity.Source.PORTAL,
    )
    return manifests, cards, proofs, proof_ids, kind_by_id, manifest_by_proof_id


def _ranking_context(driver: Driver, opportunities: list[RetainedProof]):
    today = timezone.localdate()
    start = today.replace(day=1)
    metrics = calculate_driver_metrics(start, today)
    ranked = [m for m in metrics if m.movements > 0]
    current = next((m for m in ranked if m.driver.pk == driver.pk), None)
    position = None
    gap = None
    if current:
        position = next((i for i, m in enumerate(ranked, start=1) if m.driver.pk == driver.pk), None)
        if position and position > 1:
            above = ranked[position - 2]
            gap = max(Decimal("0"), above.general_score - current.general_score).quantize(Decimal("0.1"))
    settings_obj = SystemSettings.load()
    base = current.general_score if current else Decimal("0")
    for proof in opportunities:
        projected = base
        projected_bonus = Decimal("0")
        if current:
            proof_management = current.proof_management_score
            regularity = current.regularity_score
            exact_recoveries = current.exact_recoveries
            gold_recoveries = current.gold_recoveries
            if proof.opportunity_kind == ProofPickupAttempt.Kind.GOLD:
                gold_recoveries += 1
            else:
                # Uma Retirada Exata aprovada também conta como gestão correta e
                # como resposta a uma obrigação apresentada. A projeção usa a
                # MESMA fórmula oficial, em vez de apenas somar um bônus bruto.
                managed = current.proof_management_managed + 1
                evaluated = managed + current.proof_management_failures
                proof_management = percent(managed, evaluated) if evaluated else Decimal("100")
                fulfilled = current.regularity_fulfilled + 1
                required = current.regularity_required + 1
                regularity = percent(fulfilled, required) if required else Decimal("100")
                exact_recoveries += 1
            projection = build_performance_v3_score(
                success_rate=current.success_rate,
                primary_issue_rate=Decimal("100") - current.operational_quality_score,
                quality_failure_rate=Decimal("100") - current.operational_quality_score,
                proof_management_score=proof_management,
                regularity_score=regularity,
                exact_recoveries=exact_recoveries,
                gold_recoveries=gold_recoveries,
                weights={
                    "proofs": settings_obj.driver_v3_proofs_weight,
                    "quality": settings_obj.driver_v3_quality_weight,
                    "regularity": settings_obj.driver_v3_regularity_weight,
                },
                exact_bonus=settings_obj.driver_v3_exact_recovery_bonus,
                gold_bonus=settings_obj.driver_v3_gold_recovery_bonus,
                bonus_cap=settings_obj.driver_v3_bonus_cap,
            )
            projected = projection.score
            projected_bonus = max(Decimal("0"), projection.bonus - current.recovery_bonus).quantize(Decimal("0.1"))
        projected_position = 1 + sum(1 for m in ranked if m.driver.pk != driver.pk and m.general_score > projected)
        proof.projected_score = projected
        proof.projected_position = projected_position
        proof.projected_bonus = projected_bonus
    quality_events = evaluation_events_for_driver(driver.pk, start, today, limit=30)
    negative_events = [e for e in quality_events if e.status == e.Status.DRIVER_RESPONSIBLE]
    neutral_events = [e for e in quality_events if e.status == e.Status.NOT_RESPONSIBLE]
    pending_events = [e for e in quality_events if e.status in {e.Status.PENDING, e.Status.VERIFY}]
    return {
        "ranking_metric": current,
        "ranking_position": position,
        "ranking_gap": gap,
        "ranking_period_start": start,
        "ranking_period_end": today,
        "quality_events": quality_events,
        "quality_negative_events": negative_events,
        "quality_neutral_events": neutral_events,
        "quality_pending_events": pending_events,
        "top_rewards": [
            settings_obj.top1_reward_description,
            settings_obj.top2_reward_description,
            settings_obj.top3_reward_description,
        ],
        "ranking_top3": ranked[:3],
        "score_history": score_history_for_driver(driver.pk, limit=14),
    }


@login_required
def portal_access_manage(request, pk):
    if not _staff(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    driver = get_object_or_404(Driver, pk=pk)
    access = DriverPortalAccess.objects.filter(driver=driver).first()
    if request.method == "POST":
        action = request.POST.get("action")
        before = {"active": access.active if access else None, "had_access": bool(access)}
        if action == "create":
            access, _ = DriverPortalAccess.objects.get_or_create(driver=driver)
            access.active = True
            access.save(update_fields=["active"])
            messages.success(request, "Link seguro do motorista ativado.")
        elif action == "rotate":
            access = access or DriverPortalAccess.objects.create(driver=driver)
            access.rotate()
            messages.success(request, "Link do motorista regenerado. O link anterior foi invalidado.")
        elif action == "revoke" and access:
            access.active = False
            access.save(update_fields=["active"])
            messages.success(request, "Acesso do motorista revogado.")
        AuditLog.objects.create(
            user=request.user,
            action=f"DRIVER_PORTAL_{(action or 'UNKNOWN').upper()}",
            entity="DriverPortalAccess",
            entity_id=str(driver.pk),
            before=before,
            after={"active": access.active if access else False, "had_access": bool(access)},
        )
        return redirect("driver_detail", pk=driver.pk)
    return redirect("driver_detail", pk=driver.pk)


def portal_home(request, token):
    timer = PerfTimer("portal")
    access = _portal_access(token)
    if not access:
        return render(request, "drivers/portal_invalid.html", {"invalid_token": token}, status=404)
    driver = access.driver
    selected_date = timezone.localdate()
    manifests, cards, opportunities, _, _, _ = _driver_opportunities(driver, selected_date)
    timer.mark("opportunities")
    planned = list(
        planned_manifests(selected_date)
        .filter(driver=driver)
        .select_related("driver", "vehicle")
        .order_by("number")
    )
    planned_cards = build_manifest_cards(planned, persist_available=False, operational_date=selected_date) if planned else []
    recent_submissions = list(
        ProofRecoverySubmission.objects.filter(driver=driver)
        .select_related("proof", "proof__cte", "proof__client")[:20]
    )
    recent_attempts = list(
        ProofPickupAttempt.objects.filter(driver=driver)
        .select_related("proof", "proof__cte", "proof__client")[:20]
    )
    recovered_count = RetainedProof.objects.filter(recovery_driver=driver, status=RetainedProof.Status.RECOVERED).count()
    today_moves = list(
        DeliveryMovement.objects.filter(manifest__in=manifests, driver=driver)
        .select_related("cte", "client", "address", "manifest")
        .order_by("manifest__number", "client__name")
    )
    retained_cte_ids = set(RetainedProof.objects.filter(cte_id__in=[m.cte_id for m in today_moves]).values_list("cte_id", flat=True))
    retention_candidates = [m for m in today_moves if m.cte_id not in retained_cte_ids and m.client_id]
    context = {
        "portal_access": access,
        "driver": driver,
        "selected_date": selected_date,
        "cards": cards,
        "manifests": manifests,
        "planned_cards": planned_cards,
        "opportunities": opportunities,
        "recent_submissions": recent_submissions,
        "recent_attempts": recent_attempts,
        "pending_validation_count": sum(1 for item in recent_submissions if item.status == ProofRecoverySubmission.Status.PENDING),
        "recovered_count": recovered_count,
        "delivered_today": sum(card.get("delivered", 0) for card in cards),
        "retention_candidates": retention_candidates,
        "token": token,
        "exact_count": sum(1 for p in opportunities if p.opportunity_kind == ProofPickupAttempt.Kind.EXACT),
        "gold_count": sum(1 for p in opportunities if p.opportunity_kind == ProofPickupAttempt.Kind.GOLD),
    }
    context.update(_ranking_context(driver, opportunities))
    timer.mark("ranking")
    timer.total()
    return render(request, "drivers/portal.html", context)


@require_POST
def portal_request_access(request):
    # Anti-abuso leve e compatível com Redis/LocMem. O retorno continua genérico
    # para não permitir enumeração de CPF nem revelar se o throttle foi acionado.
    remote = (request.META.get("REMOTE_ADDR") or "unknown").strip()[:80]
    throttle_key = f"portal-access-request:{remote}"
    if not cache.add(throttle_key, 1, timeout=15):
        return render(request, "drivers/portal_access_requested.html", status=202)

    cpf = "".join(ch for ch in (request.POST.get("cpf") or "") if ch.isdigit())
    phone = "".join(ch for ch in (request.POST.get("phone") or "") if ch.isdigit())[:20]
    reason = (request.POST.get("reason") or "Perdi meu link de acesso").strip()[:255]
    driver = None
    if len(cpf) == 11:
        formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        driver = Driver.objects.filter(active=True).filter(cpf__in=[cpf, formatted]).only("id", "cpf").first()
    if driver and not DriverPortalAccessRequest.objects.filter(
        driver=driver, status=DriverPortalAccessRequest.Status.PENDING
    ).exists():
        DriverPortalAccessRequest.objects.create(driver=driver, requested_phone=phone, reason=reason)
        AuditLog.objects.create(
            user=None, action="DRIVER_PORTAL_ACCESS_REQUESTED", entity="Driver", entity_id=str(driver.pk),
            before={}, after={"requested_phone": phone[-4:] if phone else ""},
        )
    # Resposta deliberadamente genérica para não revelar cadastros por CPF.
    return render(request, "drivers/portal_access_requested.html", status=202)


@require_POST
@login_required
def portal_review_access_request(request, request_pk):
    if not _staff(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    access_request = get_object_or_404(DriverPortalAccessRequest.objects.select_related("driver"), pk=request_pk)
    if access_request.status != DriverPortalAccessRequest.Status.PENDING:
        messages.info(request, "Esta solicitação já foi analisada.")
        return redirect("whatsapp_center")
    decision = request.POST.get("decision")
    access_request.reviewed_by = request.user
    access_request.reviewed_at = timezone.now()
    access_request.review_note = (request.POST.get("review_note") or "").strip()[:255]
    if decision == "approve":
        access, created = DriverPortalAccess.objects.get_or_create(driver=access_request.driver)
        if not created:
            access.rotate()
        else:
            access.active = True
            access.save(update_fields=["active"])
        access_request.status = DriverPortalAccessRequest.Status.APPROVED
        access_request.generated_access = access
        if request.POST.get("send_whatsapp"):
            from apps.messaging.models import WhatsAppMessage
            from apps.messaging.services import (
                build_general_portal_message, is_valid_whatsapp_phone,
                normalize_whatsapp_phone, public_portal_ready,
            )
            phone = normalize_whatsapp_phone(access_request.requested_phone or access_request.driver.whatsapp_phone)
            if is_valid_whatsapp_phone(phone) and public_portal_ready(request):
                path = reverse("driver_portal", args=[access.token])
                public_base = (getattr(settings, "PANEL_PUBLIC_BASE_URL", "") or "").strip()
                portal_url = public_base.rstrip("/") + path if public_base else request.build_absolute_uri(path)
                WhatsAppMessage.objects.create(
                    driver=access_request.driver,
                    operation_date=timezone.localdate(),
                    phone=phone,
                    portal_url=portal_url,
                    body=build_general_portal_message(access_request.driver, portal_url),
                    kind=WhatsAppMessage.Kind.MANUAL,
                    created_by=request.user,
                )
                access_request.sent_via_whatsapp = True
        messages.success(request, f"Novo acesso de {access_request.driver.name} aprovado e regenerado.")
    elif decision == "reject":
        access_request.status = DriverPortalAccessRequest.Status.REJECTED
        messages.success(request, "Solicitação rejeitada.")
    else:
        messages.error(request, "Decisão inválida.")
        return redirect("whatsapp_center")
    access_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "generated_access", "sent_via_whatsapp"])
    AuditLog.objects.create(
        user=request.user, action="DRIVER_PORTAL_ACCESS_REQUEST_REVIEWED", entity="DriverPortalAccessRequest",
        entity_id=str(access_request.pk), before={"status": "PENDING"},
        after={"status": access_request.status, "sent_via_whatsapp": access_request.sent_via_whatsapp},
    )
    return redirect("whatsapp_center")


@require_POST
def portal_report_retention(request, token, movement_pk):
    access = _portal_or_404(token)
    driver = access.driver
    movement = get_object_or_404(
        DeliveryMovement.objects.select_related("cte", "client", "address", "manifest"),
        pk=movement_pk, driver=driver,
    )
    evidence = _request_evidence(request)
    error = _validate_evidence(evidence, required=True)
    if error:
        messages.error(request, error)
        return redirect("driver_portal", token=token)
    now = timezone.now()
    with transaction.atomic():
        proof = RetainedProof.objects.select_for_update().filter(cte=movement.cte).first()
        if proof and (proof.original_driver_id != driver.pk or (proof.original_manifest_id and proof.original_manifest_id != movement.manifest_id)):
            messages.error(request, "Já existe uma retenção com outra origem. O coordenador precisa revisar antes de anexar nova ressalva.")
            return redirect("driver_portal", token=token)
        if not proof:
            proof = RetainedProof.objects.create(
                cte=movement.cte,
                invoice_number=movement.cte.invoice_number,
                client=movement.client,
                address=movement.address,
                original_driver=driver,
                original_manifest=movement.manifest,
                retained_at=now,
                freight_value=movement.cte.freight_value,
                merchandise_value=movement.cte.merchandise_value,
                weight_kg=movement.weight_kg or movement.cte.weight_kg,
                volumes=movement.volumes or movement.cte.volumes,
                status=RetainedProof.Status.WAITING,
                note=(request.POST.get("note") or "").strip(),
            )
        retention, _ = ProofRetention.objects.update_or_create(
            proof=proof,
            defaults={
                "driver": driver, "manifest": movement.manifest, "retained_at": now,
                "evidence": evidence, "note": (request.POST.get("note") or "").strip(),
            },
        )
    AuditLog.objects.create(
        user=None, action="PROOF_RETENTION_REPORTED_BY_DRIVER", entity="RetainedProof", entity_id=str(proof.pk),
        before={}, after={"driver_id": driver.pk, "manifest_id": movement.manifest_id, "retention_id": retention.pk},
    )
    # Atualiza imediatamente a obrigação prospectiva de ressalva para que a
    # Regularidade reflita a ação correta sem aguardar o housekeeping diário.
    sync_retention_obligations(start=movement.movement_date, end=timezone.localdate())
    snapshot_driver_scores(driver_ids=[driver.pk])
    messages.success(request, "Retenção registrada com a ressalva. O comprovante ficou disponível para acompanhamento.")
    return redirect("driver_portal", token=token)


@require_POST
def portal_pickup_action(request, token, proof_pk):
    access = _portal_or_404(token)
    driver = access.driver
    target_date = timezone.localdate()
    manifests, _cards, _proofs, allowed_ids, kind_by_id, manifest_by_proof_id = _driver_opportunities(driver, target_date)
    if proof_pk not in allowed_ids:
        raise Http404("Este comprovante não está disponível nesta operação.")
    proof = get_object_or_404(RetainedProof.objects.select_related("cte", "client"), pk=proof_pk)
    kind = kind_by_id[proof_pk]
    outcome = request.POST.get("outcome")
    valid_outcomes = {x for x, _ in ProofPickupAttempt.Outcome.choices}
    if outcome not in valid_outcomes:
        messages.error(request, "Ação de retirada inválida.")
        return redirect("driver_portal", token=token)
    note = (request.POST.get("note") or "").strip()
    evidence = _request_evidence(request)
    if outcome == ProofPickupAttempt.Outcome.RECOVERED:
        error = _validate_evidence(evidence, required=True)
        if error:
            messages.error(request, error)
            return redirect("driver_portal", token=token)
    elif outcome == ProofPickupAttempt.Outcome.NOT_RELEASED and not note:
        messages.error(request, "Informe a observação do cliente para registrar que o comprovante ainda não foi liberado.")
        return redirect("driver_portal", token=token)
    elif outcome == ProofPickupAttempt.Outcome.UNABLE and not note:
        messages.error(request, "Informe a justificativa para registrar que não foi possível tentar.")
        return redirect("driver_portal", token=token)
    else:
        error = _validate_evidence(evidence, required=False)
        if error:
            messages.error(request, error)
            return redirect("driver_portal", token=token)
    manifest = manifest_by_proof_id.get(proof_pk) or (manifests[0] if manifests else None)
    with transaction.atomic():
        locked = RetainedProof.objects.select_for_update().get(pk=proof.pk)
        attempt, _ = ProofPickupAttempt.objects.update_or_create(
            proof=locked, driver=driver, manifest=manifest, operation_date=target_date, kind=kind,
            defaults={"outcome": outcome, "note": note, "evidence": evidence or ""},
        )
        if manifest:
            mark_opportunity_responded(
                proof_id=locked.pk, driver_id=driver.pk, manifest_id=manifest.pk,
                operation_date=target_date, kind=kind, outcome=outcome,
            )
        if outcome == ProofPickupAttempt.Outcome.RECOVERED:
            if locked.recovery_submissions.filter(status=ProofRecoverySubmission.Status.PENDING).exists():
                messages.info(request, "Já existe uma recuperação aguardando validação.")
                return redirect("driver_portal", token=token)
            submission = ProofRecoverySubmission.objects.create(
                proof=locked, driver=driver, recovered_at=timezone.now(),
                status=ProofRecoverySubmission.Status.PENDING,
                source=ProofRecoverySubmission.Source.DRIVER_PORTAL,
                evidence=evidence, note=note,
            )
            attempt.submission = submission
            attempt.save(update_fields=["submission"])
            locked.status = RetainedProof.Status.AWAITING_VALIDATION
            locked.save(update_fields=["status", "updated_at"])
            messages.success(request, "Recuperação enviada. A nota só muda depois da validação do coordenador.")
        elif outcome == ProofPickupAttempt.Outcome.NOT_RELEASED:
            messages.success(request, "Registrado como ainda não liberado. Isso não gera penalização.")
        else:
            messages.success(request, "Justificativa registrada para auditoria, sem penalização automática.")
    AuditLog.objects.create(
        user=None, action="PROOF_PICKUP_ATTEMPT_BY_DRIVER", entity="RetainedProof", entity_id=str(proof.pk),
        before={}, after={"driver_id": driver.pk, "kind": kind, "outcome": outcome, "attempt_id": attempt.pk},
    )
    snapshot_driver_scores(driver_ids=[driver.pk])
    return redirect("driver_portal", token=token)


@require_POST
def portal_submit_proof(request, token, proof_pk):
    # Compatibilidade com links/formulários da v0.8.x: o antigo "enviar" equivale
    # a RETIREI e passa pelo fluxo auditável V3.
    if "outcome" not in request.POST:
        request.POST = request.POST.copy()
        request.POST["outcome"] = ProofPickupAttempt.Outcome.RECOVERED
    return portal_pickup_action(request, token, proof_pk)
