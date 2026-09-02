from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.models import AuditLog
from apps.core.services import manifests_for_operational_date, planned_manifests
from apps.operations.services import build_manifest_cards, opportunities_summary
from apps.proofs.models import ProofRecoverySubmission, RetainedProof
from .models import Driver, DriverPortalAccess

MAX_EVIDENCE_BYTES = 12 * 1024 * 1024
ALLOWED_EVIDENCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
OPEN_PROOF_STATUSES = {
    RetainedProof.Status.WAITING,
    RetainedProof.Status.AVAILABLE,
    RetainedProof.Status.RECOVERING,
}


def _staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser or user.groups.filter(name__iexact="Coordenador").exists())


def _portal_or_404(token: str) -> DriverPortalAccess:
    access = get_object_or_404(
        DriverPortalAccess.objects.select_related("driver"), token=token, active=True
    )
    access.last_used_at = timezone.now()
    access.save(update_fields=["last_used_at"])
    return access


def _driver_opportunities(driver: Driver, target_date=None):
    target_date = target_date or timezone.localdate()
    manifests = list(
        manifests_for_operational_date(target_date)
        .filter(driver=driver)
        .exclude(status__iexact="CANCELADO")
        .select_related("driver", "vehicle")
        .order_by("number")
    )
    cards = build_manifest_cards(
        manifests, persist_available=False, operational_date=target_date
    )
    exact_ids, regional_ids = opportunities_summary(cards)
    proof_ids = set(exact_ids) | set(regional_ids)
    proofs = list(
        RetainedProof.objects.filter(pk__in=proof_ids, status__in=OPEN_PROOF_STATUSES)
        .select_related("cte", "client", "address", "original_driver")
        .order_by("-retained_at")
    )
    kind_by_id = {pk: "CLIENTE" for pk in exact_ids}
    for pk in regional_ids:
        kind_by_id.setdefault(pk, "REGIAO")
    for proof in proofs:
        proof.opportunity_kind = kind_by_id.get(proof.pk, "REGIAO")
    return manifests, cards, proofs, proof_ids


@login_required
def portal_access_manage(request, pk):
    if not _staff(request.user):
        return HttpResponseForbidden("Acesso restrito.")
    driver = get_object_or_404(Driver, pk=pk)
    access = DriverPortalAccess.objects.filter(driver=driver).first()
    if request.method == "POST":
        action = request.POST.get("action")
        before = {
            "active": access.active if access else None,
            "had_access": bool(access),
        }
        if action == "create":
            access, _ = DriverPortalAccess.objects.get_or_create(driver=driver)
            access.active = True
            access.save(update_fields=["active"])
            messages.success(request, "Link seguro do motorista ativado.")
        elif action == "rotate":
            if not access:
                access = DriverPortalAccess.objects.create(driver=driver)
            else:
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
    access = _portal_or_404(token)
    driver = access.driver
    selected_date = timezone.localdate()
    manifests, cards, opportunities, _ = _driver_opportunities(driver, selected_date)
    planned = list(
        planned_manifests(selected_date)
        .filter(driver=driver)
        .select_related("driver", "vehicle")
        .order_by("number")
    )
    planned_cards = build_manifest_cards(planned, persist_available=False, operational_date=selected_date) if planned else []
    recent_submissions = (
        ProofRecoverySubmission.objects.filter(driver=driver)
        .select_related("proof", "proof__cte", "proof__client")[:20]
    )
    recovered_count = RetainedProof.objects.filter(recovery_driver=driver, status=RetainedProof.Status.RECOVERED).count()
    return render(
        request,
        "drivers/portal.html",
        {
            "portal_access": access,
            "driver": driver,
            "selected_date": selected_date,
            "cards": cards,
            "manifests": manifests,
            "planned_cards": planned_cards,
            "opportunities": opportunities,
            "recent_submissions": recent_submissions,
            "recovered_count": recovered_count,
            "delivered_today": sum(card.get("delivered", 0) for card in cards),
            "token": token,
        },
    )


@require_POST
def portal_submit_proof(request, token, proof_pk):
    access = _portal_or_404(token)
    driver = access.driver
    _, _, _, allowed_ids = _driver_opportunities(driver, timezone.localdate())
    if proof_pk not in allowed_ids:
        raise Http404("Este comprovante não está disponível como oportunidade nesta rota.")
    # A câmera e o seletor de arquivo são separados no mobile. Mantemos
    # `evidence` como fallback para links/telas antigos durante a atualização.
    evidence = (
        request.FILES.get("evidence_camera")
        or request.FILES.get("evidence_file")
        or request.FILES.get("evidence")
    )
    if not evidence:
        messages.error(request, "Envie uma foto ou PDF do comprovante para validação.")
        return redirect("driver_portal", token=token)
    ext = Path(evidence.name).suffix.lower()
    if ext not in ALLOWED_EVIDENCE_EXTENSIONS or evidence.size > MAX_EVIDENCE_BYTES:
        messages.error(request, "Evidência inválida. Use JPG, PNG, WEBP ou PDF de até 12 MB.")
        return redirect("driver_portal", token=token)

    with transaction.atomic():
        proof = RetainedProof.objects.select_for_update().filter(pk=proof_pk).first()
        if proof is None or proof.status not in OPEN_PROOF_STATUSES:
            messages.info(request, "Este comprovante já não está disponível para novo envio.")
            return redirect("driver_portal", token=token)
        if proof.recovery_submissions.filter(status=ProofRecoverySubmission.Status.PENDING).exists():
            messages.info(request, "Já existe uma evidência aguardando validação para este comprovante.")
            return redirect("driver_portal", token=token)
        submission = ProofRecoverySubmission.objects.create(
            proof=proof,
            driver=driver,
            recovered_at=timezone.now(),
            status=ProofRecoverySubmission.Status.PENDING,
            source=ProofRecoverySubmission.Source.DRIVER_PORTAL,
            evidence=evidence,
            note=(request.POST.get("note") or "").strip(),
        )
        proof.status = RetainedProof.Status.AWAITING_VALIDATION
        proof.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        user=None,
        action="PROOF_RECOVERY_SUBMITTED_BY_DRIVER",
        entity="RetainedProof",
        entity_id=str(proof.pk),
        before={"status": "OPEN"},
        after={"status": proof.status, "driver_id": driver.pk, "submission_id": submission.pk},
    )
    messages.success(request, "Comprovante enviado. A recuperação ficará concluída após validação do coordenador.")
    return redirect("driver_portal", token=token)
