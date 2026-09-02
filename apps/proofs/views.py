from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.models import SystemSettings
from apps.drivers.models import Driver
from apps.operations.services import refresh_today_opportunities
from .models import ProofRecoverySubmission, RetainedProof


MAX_EVIDENCE_BYTES = 12 * 1024 * 1024
OPEN_STATUSES = [
    RetainedProof.Status.WAITING,
    RetainedProof.Status.AVAILABLE,
    RetainedProof.Status.RECOVERING,
    RetainedProof.Status.AWAITING_VALIDATION,
]


def _can_recover(user):
    return (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name__iexact="Coordenador").exists()
    )


def _safe_return(request, selected=None):
    params = request.POST.get("return_query", "").strip().lstrip("?")
    if selected:
        extra = {"selected": selected}
        if params:
            return f"/comprovantes/?{params}&{urlencode(extra)}"
        return f"/comprovantes/?{urlencode(extra)}"
    return f"/comprovantes/?{params}" if params else "/comprovantes/"


def _parse_date(value: str):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _recovery_datetime(raw_date: str | None):
    recovered_date = _parse_date(raw_date) or timezone.localdate()
    if recovered_date > timezone.localdate():
        raise ValueError("A recuperação não pode ser registrada em data futura.")
    if recovered_date == timezone.localdate():
        return timezone.now()
    return timezone.make_aware(
        datetime.combine(recovered_date, time(12, 0)),
        timezone.get_current_timezone(),
    )


def _validate_evidence(upload):
    if not upload:
        return None
    if upload.size > MAX_EVIDENCE_BYTES:
        return "A evidência deve ter no máximo 12 MB."
    suffix = (upload.name.rsplit(".", 1)[-1] if "." in upload.name else "").lower()
    if suffix not in {"jpg", "jpeg", "png", "webp", "pdf"}:
        return "Envie evidência em JPG, PNG, WEBP ou PDF."
    return None


@login_required
def index(request):
    refresh_today_opportunities()
    base_qs = RetainedProof.objects.select_related(
        "cte", "client", "address", "original_driver", "recovery_driver"
    ).order_by("-retained_at")

    q = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()
    district = request.GET.get("district", "").strip()
    status = request.GET.get("status", "").strip()
    driver_id = request.GET.get("driver", "").strip()
    recovery_driver_id = request.GET.get("recovery_driver", "").strip()
    age = request.GET.get("age", "").strip()
    period = request.GET.get("period", "").strip()
    start_raw = request.GET.get("start", "").strip()
    end_raw = request.GET.get("end", "").strip()
    sla = request.GET.get("sla", "").strip()
    evidence = request.GET.get("evidence", "").strip()

    qs = base_qs
    if q:
        qs = qs.filter(
            Q(cte__ctrc__icontains=q)
            | Q(invoice_number__icontains=q)
            | Q(client__name__icontains=q)
            | Q(original_manifest__number__icontains=q)
        )
    if city:
        qs = qs.filter(address__city=city)
    if district:
        qs = qs.filter(address__district=district)
    if status == "ACTIVE":
        qs = qs.filter(status__in=OPEN_STATUSES)
    elif status:
        qs = qs.filter(status=status)
    if driver_id.isdigit():
        qs = qs.filter(original_driver_id=int(driver_id))
    if recovery_driver_id.isdigit():
        qs = qs.filter(recovery_driver_id=int(recovery_driver_id))

    today = timezone.localdate()
    # Filtro temporal é opcional; por padrão a Central continua exibindo todo o
    # estoque, para não esconder comprovante antigo apenas por ter virado o mês.
    start = _parse_date(start_raw)
    end = _parse_date(end_raw)
    if start and end:
        if start > end:
            start, end = end, start
        qs = qs.filter(retained_at__date__range=(start, end))
    elif period:
        if period == "today":
            start = end = today
        elif period == "7d":
            start, end = today - timedelta(days=6), today
        elif period == "week":
            start, end = today - timedelta(days=today.weekday()), today
        elif period == "month":
            start, end = today.replace(day=1), today
        elif period == "30d":
            start, end = today - timedelta(days=29), today
        if start and end:
            qs = qs.filter(retained_at__date__range=(start, end))

    age_ranges = {
        "0-1": (0, 1),
        "2-3": (2, 3),
        "4-7": (4, 7),
        "8-15": (8, 15),
        "16-30": (16, 30),
        "30+": (31, None),
    }
    if age in age_ranges:
        min_days, max_days = age_ranges[age]
        qs = qs.filter(retained_at__date__lte=today - timedelta(days=min_days))
        if max_days is not None:
            qs = qs.filter(retained_at__date__gte=today - timedelta(days=max_days))

    settings_obj = SystemSettings.load()
    if sla == "overdue":
        qs = qs.filter(
            status__in=OPEN_STATUSES,
            retained_at__date__lt=today - timedelta(days=int(settings_obj.proof_sla_days or 7)),
        )
    evidence_proof_ids = ProofRecoverySubmission.objects.exclude(evidence="").values_list("proof_id", flat=True)
    if evidence == "yes":
        qs = qs.filter(pk__in=evidence_proof_ids)
    elif evidence == "no":
        qs = qs.exclude(pk__in=evidence_proof_ids)

    filtered_qs = qs
    page = Paginator(filtered_qs, 25).get_page(request.GET.get("page"))

    critical_threshold = today - timedelta(days=settings_obj.critical_days)
    kpis = filtered_qs.aggregate(
        critical=Count("id", filter=Q(status__in=OPEN_STATUSES, retained_at__date__lt=critical_threshold)),
        waiting=Count("id", filter=Q(status=RetainedProof.Status.WAITING)),
        available=Count("id", filter=Q(status=RetainedProof.Status.AVAILABLE)),
        validation=Count("id", filter=Q(status=RetainedProof.Status.AWAITING_VALIDATION)),
        recovered=Count("id", filter=Q(status=RetainedProof.Status.RECOVERED)),
        value=Sum("freight_value", filter=Q(status__in=OPEN_STATUSES)),
    )

    selected = None
    selected_client_pending = 0
    selected_submissions = []
    if request.GET.get("selected"):
        selected = get_object_or_404(
            RetainedProof.objects.select_related(
                "cte", "client", "address", "original_driver", "recovery_driver", "original_manifest"
            ),
            pk=request.GET["selected"],
        )
        selected_client_pending = RetainedProof.objects.filter(
            client=selected.client,
            status__in=OPEN_STATUSES,
        ).count()
        selected_submissions = list(
            selected.recovery_submissions.select_related("driver", "submitted_by", "validated_by").all()[:10]
        )

    query_without_page = request.GET.copy()
    query_without_page.pop("page", None)
    query_without_page.pop("selected", None)

    return render(
        request,
        "proofs/index.html",
        {
            "page_obj": page,
            "critical_count": kpis["critical"] or 0,
            "waiting_count": kpis["waiting"] or 0,
            "available_count": kpis["available"] or 0,
            "validation_count": kpis["validation"] or 0,
            "recovered_count": kpis["recovered"] or 0,
            "retained_value": kpis["value"] or Decimal("0"),
            "selected_proof": selected,
            "selected_client_pending": selected_client_pending,
            "selected_submissions": selected_submissions,
            "drivers": Driver.objects.filter(active=True, is_test=False).order_by("name"),
            "cities": RetainedProof.objects.exclude(address__city="")
            .values_list("address__city", flat=True).distinct().order_by("address__city"),
            "districts": RetainedProof.objects.exclude(address__district="")
            .values_list("address__district", flat=True).distinct().order_by("address__district"),
            "status_choices": RetainedProof.Status.choices,
            "can_recover": _can_recover(request.user),
            "today": today,
            "proof_sla_days": settings_obj.proof_sla_days,
            "filters": {
                "q": q, "city": city, "district": district, "status": status,
                "driver": driver_id, "recovery_driver": recovery_driver_id,
                "age": age, "period": period, "start": start_raw, "end": end_raw,
                "sla": sla, "evidence": evidence,
            },
            "query_without_page": query_without_page.urlencode(),
        },
    )


@login_required
def recover(request, pk):
    """Registro direto pelo coordenador — motorista recuperador é explícito."""
    if request.method != "POST":
        return redirect("proofs")
    if not _can_recover(request.user):
        return HttpResponseForbidden("Sem permissão para recuperar comprovantes.")

    driver_id = request.POST.get("recovery_driver", "")
    if not driver_id.isdigit():
        messages.error(request, "Informe o motorista que recuperou o comprovante.")
        return redirect(_safe_return(request, pk))
    driver = get_object_or_404(Driver, pk=int(driver_id), is_test=False)
    try:
        recovered_at = _recovery_datetime(request.POST.get("recovered_at"))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_safe_return(request, pk))
    evidence = request.FILES.get("evidence")
    evidence_error = _validate_evidence(evidence)
    if evidence_error:
        messages.error(request, evidence_error)
        return redirect(_safe_return(request, pk))
    note = request.POST.get("note", "").strip()

    # Lock do comprovante dentro da mesma transação que grava a recuperação.
    # Isso impede que dois coordenadores concluam o mesmo comprovante em paralelo.
    with transaction.atomic():
        proof = (
            RetainedProof.objects.select_for_update()
            .select_related("original_driver", "recovery_driver")
            .filter(pk=pk)
            .first()
        )
        if proof is None:
            messages.info(request, "Este comprovante não existe mais.")
            return redirect("proofs")
        if proof.status == RetainedProof.Status.RECOVERED:
            messages.info(request, "Este comprovante já está recuperado.")
            return redirect(_safe_return(request, pk))
        if proof.status == RetainedProof.Status.CANCELED:
            messages.error(request, "Comprovante cancelado não pode ser recuperado sem reabertura auditada.")
            return redirect(_safe_return(request, pk))
        if recovered_at.date() < proof.retained_at.date():
            messages.error(request, "A recuperação não pode ocorrer antes da retenção.")
            return redirect(_safe_return(request, pk))

        before = {
            "status": proof.status,
            "recovered_at": str(proof.recovered_at),
            "recovery_driver": proof.recovery_driver_id,
            "confirmed_by": proof.confirmed_by_id,
            "note": proof.note,
        }
        submission = ProofRecoverySubmission.objects.create(
            proof=proof,
            driver=driver,
            recovered_at=recovered_at,
            status=ProofRecoverySubmission.Status.APPROVED,
            source=ProofRecoverySubmission.Source.COORDINATOR,
            evidence=evidence or "",
            note=note,
            submitted_by=request.user,
            validated_by=request.user,
            validated_at=timezone.now(),
            validation_note="Registro direto pelo coordenador/responsável.",
        )
        proof.status = RetainedProof.Status.RECOVERED
        proof.recovered_at = recovered_at
        proof.recovery_driver = driver
        proof.confirmed_by = request.user
        proof.note = note
        proof.save(update_fields=["status", "recovered_at", "recovery_driver", "confirmed_by", "note", "updated_at"])
        # Qualquer evidência pendente anterior perde validade depois que o
        # coordenador registra uma recuperação direta. Mantemos o histórico.
        ProofRecoverySubmission.objects.filter(
            proof=proof, status=ProofRecoverySubmission.Status.PENDING
        ).exclude(pk=submission.pk).update(
            status=ProofRecoverySubmission.Status.REJECTED,
            validated_by=request.user, validated_at=timezone.now(),
            validation_note="Encerrada automaticamente: recuperação registrada diretamente pelo coordenador.",
        )
        AuditLog.objects.create(
            user=request.user,
            action="PROOF_RECOVERED",
            entity="RetainedProof",
            entity_id=str(proof.pk),
            before=before,
            after={
                "status": proof.status,
                "recovered_at": str(proof.recovered_at),
                "recovery_driver": driver.pk,
                "confirmed_by": request.user.pk,
                "submission": submission.pk,
                "note": proof.note,
            },
        )
    messages.success(request, f"Comprovante recuperado por {driver.name} e registrado no histórico.")
    return redirect(_safe_return(request, pk))


@login_required
def validate_submission(request, submission_pk):
    if request.method != "POST":
        return redirect("proofs")
    if not _can_recover(request.user):
        return HttpResponseForbidden("Sem permissão para validar recuperação.")

    action = request.POST.get("decision", "approve")
    with transaction.atomic():
        submission = (
            ProofRecoverySubmission.objects.select_for_update()
            .select_related("driver")
            .filter(pk=submission_pk)
            .first()
        )
        if submission is None:
            messages.info(request, "Esta evidência não existe mais.")
            return redirect("proofs")
        proof = RetainedProof.objects.select_for_update().filter(pk=submission.proof_id).first()
        if proof is None:
            messages.info(request, "O comprovante associado não existe mais.")
            return redirect("proofs")
        if submission.status != ProofRecoverySubmission.Status.PENDING:
            messages.info(request, "Esta evidência já foi analisada.")
            return redirect(_safe_return(request, proof.pk))
        if proof.status == RetainedProof.Status.CANCELED:
            messages.error(request, "Comprovante cancelado não pode ser validado sem reabertura auditada.")
            return redirect(_safe_return(request, proof.pk))

        if action in {"reject", "request_new"}:
            reason = (request.POST.get("rejection_reason") or request.POST.get("validation_note") or "").strip()
            if action == "request_new" and not reason:
                reason = "Solicitada nova foto/evidência pelo coordenador."
            submission.status = ProofRecoverySubmission.Status.REJECTED
            submission.validated_by = request.user
            submission.validated_at = timezone.now()
            submission.validation_note = reason
            submission.save(update_fields=["status", "validated_by", "validated_at", "validation_note"])
            has_other_pending = ProofRecoverySubmission.objects.filter(
                proof=proof, status=ProofRecoverySubmission.Status.PENDING
            ).exclude(pk=submission.pk).exists()
            if not has_other_pending and proof.status == RetainedProof.Status.AWAITING_VALIDATION:
                proof.status = RetainedProof.Status.WAITING
                proof.save(update_fields=["status", "updated_at"])
            AuditLog.objects.create(
                user=request.user, action="PROOF_RECOVERY_REJECTED", entity="ProofRecoverySubmission",
                entity_id=str(submission.pk), before={"status": "PENDING"},
                after={"status": "REJECTED", "reason": reason, "request_new": action == "request_new"},
            )
            messages.info(request, "Nova evidência solicitada." if action == "request_new" else "Evidência rejeitada; comprovante voltou para aguardando retirada.")
        else:
            if proof.status == RetainedProof.Status.RECOVERED:
                messages.info(request, "Este comprovante já foi recuperado por outra validação.")
                return redirect(_safe_return(request, proof.pk))
            before = {"status": proof.status, "recovery_driver": proof.recovery_driver_id, "recovered_at": str(proof.recovered_at)}
            submission.status = ProofRecoverySubmission.Status.APPROVED
            submission.validated_by = request.user
            submission.validated_at = timezone.now()
            submission.validation_note = request.POST.get("validation_note", "").strip()
            submission.save(update_fields=["status", "validated_by", "validated_at", "validation_note"])
            proof.status = RetainedProof.Status.RECOVERED
            proof.recovery_driver = submission.driver
            proof.recovered_at = submission.recovered_at
            proof.confirmed_by = request.user
            proof.note = submission.note
            proof.save(update_fields=["status", "recovery_driver", "recovered_at", "confirmed_by", "note", "updated_at"])
            # Evidências concorrentes que chegaram antes da aprovação permanecem no
            # histórico, mas deixam de poder ser aprovadas como uma segunda recuperação.
            ProofRecoverySubmission.objects.filter(
                proof=proof, status=ProofRecoverySubmission.Status.PENDING
            ).exclude(pk=submission.pk).update(
                status=ProofRecoverySubmission.Status.REJECTED,
                validated_by=request.user, validated_at=timezone.now(),
                validation_note="Encerrada automaticamente: outra evidência deste comprovante foi aprovada.",
            )
            AuditLog.objects.create(
                user=request.user, action="PROOF_RECOVERY_APPROVED", entity="RetainedProof",
                entity_id=str(proof.pk), before=before,
                after={"status": proof.status, "recovery_driver": proof.recovery_driver_id, "recovered_at": str(proof.recovered_at), "submission": submission.pk},
            )
            messages.success(request, f"Recuperação validada para {submission.driver.name}.")
    return redirect(_safe_return(request, proof.pk))
