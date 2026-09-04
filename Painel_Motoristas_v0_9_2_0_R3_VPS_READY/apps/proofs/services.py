from __future__ import annotations

from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.cache import invalidate_operational_cache
from apps.core.perf import PerfTimer
from apps.operations.models import DeliveryOccurrence
from apps.ssw.parsers import clean, is_delivered_occurrence, is_retention_occurrence, normalize_text
from .models import RetainedProof

AUTO_PREFIX = "[SSW AUTO]"


def _auto_note(action, occurred_at=None):
    when = timezone.localtime(occurred_at).strftime("%d/%m/%Y %H:%M") if occurred_at else "data não informada"
    return f"{AUTO_PREFIX} {action} pelo estado consolidado atual do CTRC em {when}."


def _manual_recovery(proof):
    return bool(
        proof.status == RetainedProof.Status.RECOVERED
        and (proof.recovery_driver_id is not None or proof.confirmed_by_id is not None)
    )


def _current_snapshot_for_proofs(proofs):
    cte_ids = [p.cte_id for p in proofs]
    by_cte = {}
    rows = (
        DeliveryOccurrence.objects.filter(cte_id__in=cte_ids, source="SSW_CTRC")
        .only("id", "cte_id", "code", "description", "occurred_at", "imported_at")
        .order_by("cte_id", "-imported_at", "-id")
    )
    for row in rows:
        by_cte.setdefault(row.cte_id, row)
    return by_cte


def classify_retained_proof_current_state(proof, occurrence=None):
    """Classifica pela fotografia atual, não por uma cronologia inventada.

    ``CTe.current_status`` é a fotografia consolidada mais recente mantida pelo
    importador. Uma ``DeliveryOccurrence`` pode ter ``imported_at`` antigo (o
    ``get_or_create`` reaproveita o mesmo fato quando o SSW volta a um status já
    visto), por isso nunca misturamos o *code* de uma ocorrência histórica com a
    descrição atual do CT-e. Quando existe ``current_status`` ele governa a
    classificação; a ocorrência só complementa código/data se descreve o mesmo
    estado normalizado.
    """
    current_description = clean(proof.cte.current_status)
    occurrence_description = clean(getattr(occurrence, "description", ""))
    occurrence_code = clean(getattr(occurrence, "code", ""))

    if current_description:
        description = current_description
        same_snapshot = clean(occurrence_description) and normalize_text(occurrence_description) == normalize_text(current_description)
        code = occurrence_code if same_snapshot else ""
        occurred_at = getattr(occurrence, "occurred_at", None) if same_snapshot else None
    else:
        description = occurrence_description
        code = occurrence_code
        occurred_at = getattr(occurrence, "occurred_at", None)

    if is_delivered_occurrence(code, description):
        return RetainedProof.Status.RECOVERED, "SSW", code, description, occurred_at
    if is_retention_occurrence(code, description):
        return RetainedProof.Status.WAITING, "", code, description, occurred_at
    if code or description:
        return RetainedProof.Status.TRACKING, "", code, description, occurred_at
    return proof.status, proof.resolution_source, code, description, occurred_at


def reconcile_retained_proofs(*, apply=False, user=None, limit=None):
    timer = PerfTimer("proofs.reconcile")
    qs = (
        RetainedProof.objects.exclude(status=RetainedProof.Status.CANCELED)
        .select_related("cte", "original_driver", "original_manifest")
        .order_by("pk")
    )
    if limit:
        qs = qs[:limit]
    proofs = list(qs)
    current = _current_snapshot_for_proofs(proofs)
    changes = []
    counters = defaultdict(int)

    for proof in proofs:
        if _manual_recovery(proof):
            counters["manual_preserved"] += 1
            continue
        desired, resolution_source, code, description, occurred_at = classify_retained_proof_current_state(
            proof, current.get(proof.cte_id)
        )
        before = {
            "status": proof.status,
            "recovered_at": proof.recovered_at.isoformat() if proof.recovered_at else None,
            "recovery_driver_id": proof.recovery_driver_id,
            "resolution_source": proof.resolution_source,
            "last_ssw_code": proof.last_ssw_code,
            "last_ssw_description": proof.last_ssw_description,
        }
        changed = False
        if proof.last_ssw_code != code:
            proof.last_ssw_code = code
            changed = True
        if proof.last_ssw_description != description:
            proof.last_ssw_description = description
            changed = True
        if proof.last_ssw_at != occurred_at:
            proof.last_ssw_at = occurred_at
            changed = True

        if desired == RetainedProof.Status.RECOVERED:
            if proof.status != desired:
                proof.status = desired
                changed = True
            # A data informada pelo SSW pode ser retroativamente corrigida. Ela é
            # preservada como evidência; não é comparada contra retained_at para
            # vetar a baixa nem é usada para inventar recovery_driver.
            if proof.recovered_at != occurred_at:
                proof.recovered_at = occurred_at
                changed = True
            if proof.recovery_driver_id is not None:
                proof.recovery_driver = None
                changed = True
            if proof.confirmed_by_id is not None:
                proof.confirmed_by = None
                changed = True
            if proof.resolution_source != "SSW":
                proof.resolution_source = "SSW"
                changed = True
            note = _auto_note("Resolvido automaticamente pelo SSW", occurred_at)
            if not proof.note or proof.note.startswith(AUTO_PREFIX):
                if proof.note != note:
                    proof.note = note
                    changed = True
            counters["resolved_ssw"] += int(changed)
        elif desired == RetainedProof.Status.WAITING:
            if proof.status in {RetainedProof.Status.RECOVERED, RetainedProof.Status.TRACKING, RetainedProof.Status.VERIFY}:
                proof.status = desired
                proof.recovered_at = None
                proof.recovery_driver = None
                proof.confirmed_by = None
                proof.resolution_source = ""
                note = _auto_note("Retenção confirmada", occurred_at)
                if not proof.note or proof.note.startswith(AUTO_PREFIX):
                    proof.note = note
                changed = True
                counters["reactivated"] += 1
        elif desired == RetainedProof.Status.TRACKING:
            if proof.status != RetainedProof.Status.TRACKING:
                proof.status = RetainedProof.Status.TRACKING
                proof.recovered_at = None
                proof.recovery_driver = None
                proof.confirmed_by = None
                proof.resolution_source = ""
                note = _auto_note("Acompanhando alteração do SSW", occurred_at)
                if not proof.note or proof.note.startswith(AUTO_PREFIX):
                    proof.note = note
                changed = True
                counters["tracking"] += 1

        if changed:
            proof.updated_at = timezone.now()
            changes.append((proof, before))

    if apply and changes:
        with transaction.atomic():
            RetainedProof.objects.bulk_update(
                [p for p, _ in changes],
                [
                    "status", "recovered_at", "recovery_driver", "confirmed_by", "note", "resolution_source",
                    "last_ssw_code", "last_ssw_description", "last_ssw_at", "updated_at",
                ],
                batch_size=500,
            )
            AuditLog.objects.bulk_create([
                AuditLog(
                    user=user,
                    action="PROOF_RECONCILED_FROM_SSW_CURRENT_STATE",
                    entity="RetainedProof",
                    entity_id=str(proof.pk),
                    before=before,
                    after={
                        "status": proof.status,
                        "recovered_at": proof.recovered_at.isoformat() if proof.recovered_at else None,
                        "recovery_driver_id": proof.recovery_driver_id,
                        "resolution_source": proof.resolution_source,
                        "last_ssw_code": proof.last_ssw_code,
                        "last_ssw_description": proof.last_ssw_description,
                    },
                ) for proof, before in changes
            ], batch_size=500)
        invalidate_operational_cache("retained-proofs-reconciled")
    result = {
        "scanned": len(proofs),
        "changed": len(changes),
        "applied": bool(apply),
        **dict(counters),
    }
    timer.total()
    return result
