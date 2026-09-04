from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.core.cache import cache
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.cache import invalidate_operational_cache
from apps.operations.models import DeliveryMovement, DeliveryOccurrence
from apps.proofs.models import ProofPickupAttempt, ProofPickupOpportunity, ProofRecoverySubmission, ProofRetention, ProofRetentionObligation, RetainedProof
from .models import Driver, DriverQualityEvent

ROM13_TEXT = "ENTREGA PREJUDICADA PELO HORARIO"
ROM85_TEXT = "SAIDA PARA ENTREGA"
# Marco oficial homologado para a Nota Geral V3. Eventos anteriores continuam
# no histórico operacional, mas não viram pendência nem afetam o ranking.
V3_ROLLOUT_DATE = date(2026, 9, 1)


SNAPSHOT_METRIC_KEY = "_metric_v1"
SNAPSHOT_LOCK_PREFIX = "painel:ranking-snapshot-build"

# Campos Decimal do DriverMetric. O payload do snapshot é JSON e por isso
# armazena esses valores como string para não perder precisão.
_METRIC_DECIMAL_FIELDS = {
    "weight_kg", "freight", "retained_value", "operational_index", "effort_index",
    "score", "recovered_freight_value", "recovery_bonus", "avg_proof_days",
    "median_proof_days", "success_rate", "first_attempt_rate", "clean_delivery_rate",
    "retention_rate", "time_window_rate", "productivity_score", "performance_score",
    "ranking_score", "confidence_factor", "team_quality_mean", "general_score",
    "proof_management_score", "operational_quality_score", "regularity_score",
}


def _metric_to_payload(metric) -> dict:
    """Serializa a fotografia completa usada pelas telas rápidas.

    DriverScoreSnapshot já existia para auditoria. A v0.9.2 passa a guardar no
    mesmo JSON tudo que o Dashboard/Ranking precisam para que uma invalidação de
    cache nunca obrigue o usuário a reconstruir milhares de movimentos.
    """
    from dataclasses import fields
    payload = {}
    for field in fields(metric):
        if field.name == "driver":
            continue
        payload[field.name] = _json_safe(getattr(metric, field.name))
    return payload


def load_driver_score_snapshots(period_start: date, period_end: date, *, driver_ids=None):
    """Reconstrói DriverMetric a partir de snapshots persistentes.

    Retorna None quando a fotografia exata ainda não foi materializada. O
    chamador então pode recalcular fora da request (startup/import/worker).
    """
    from apps.core.services import DriverMetric
    from .models import DriverScoreSnapshot

    qs = DriverScoreSnapshot.objects.filter(
        score_date=period_end,
        period_start=period_start,
        period_end=period_end,
    ).select_related("driver")
    if driver_ids is not None:
        ids = {int(pk) for pk in driver_ids if pk}
        qs = qs.filter(driver_id__in=ids)
    rows = list(qs)
    if not rows:
        return None

    metrics = []
    for row in rows:
        packed = (row.breakdown or {}).get(SNAPSHOT_METRIC_KEY)
        if not isinstance(packed, dict):
            # Snapshot antigo contém só o breakdown explicativo e não serve
            # como fotografia completa de navegação.
            return None
        data = dict(packed)
        for name in _METRIC_DECIMAL_FIELDS:
            if name in data and data[name] is not None:
                data[name] = Decimal(str(data[name]))
        data["driver"] = row.driver
        # Garantias para snapshots produzidos por builds intermediárias.
        data.setdefault("general_score", row.general_score)
        data.setdefault("performance_score", row.general_score)
        data.setdefault("ranking_score", row.general_score)
        data.setdefault("score", row.general_score)
        data.setdefault("proof_management_score", row.proof_management_score)
        data.setdefault("operational_quality_score", row.operational_quality_score)
        data.setdefault("regularity_score", row.regularity_score)
        data.setdefault("recovery_bonus", row.recovery_bonus)
        data.setdefault("evaluation_attempts", row.attempts)
        data.setdefault("eligible", row.eligible)
        metrics.append(DriverMetric(**data))

    metrics.sort(
        key=lambda m: (m.eligible, m.ranking_score, m.performance_score, m.movements),
        reverse=True,
    )
    return metrics


def _snapshot_build_lock(period_start: date, period_end: date, driver_ids=None) -> tuple[str, str] | None:
    suffix = "all" if driver_ids is None else ",".join(str(x) for x in sorted({int(v) for v in driver_ids if v}))
    key = f"{SNAPSHOT_LOCK_PREFIX}:{period_start}:{period_end}:{suffix}"
    token = f"{timezone.now().timestamp()}"
    if cache.add(key, token, timeout=180):
        return key, token
    return None


def _release_snapshot_lock(lock):
    if not lock:
        return
    key, token = lock
    # Não apagar lock que já expirou e foi adquirido por outro processo.
    if cache.get(key) == token:
        cache.delete(key)


def evaluation_v3_start_date() -> date:
    from apps.core.models import SystemSettings
    configured = SystemSettings.load().driver_v3_actions_activation_date
    return configured or V3_ROLLOUT_DATE


def _norm(value: str | None) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.upper().split())


def is_rom13(code, description) -> bool:
    return str(code or "").strip() == "13" or ROM13_TEXT in _norm(description)


def coordinator_user(user) -> bool:
    return bool(user and user.is_authenticated and (
        user.is_staff or user.is_superuser or user.groups.filter(name__iexact="Coordenador").exists()
    ))


def _operation_dates_for_movements(movements: list[DeliveryMovement]) -> dict[int, date]:
    ids = [m.pk for m in movements]
    result = {m.pk: m.movement_date for m in movements}
    if not ids:
        return result
    exits = (
        DeliveryOccurrence.objects.filter(movement_id__in=ids, source="SSW_ROMANEIO", occurred_at__isnull=False)
        .filter(Q(code="85") | Q(description__icontains="SAIDA PARA ENTREGA"))
        .values_list("movement_id", "occurred_at")
        .order_by("occurred_at", "pk")
    )
    seen = set()
    for movement_id, occurred_at in exits:
        # A data operacional canônica usa a PRIMEIRA saída 85 da tentativa.
        # Repetições posteriores do mesmo fato não podem migrar a tentativa.
        if movement_id in result and movement_id not in seen:
            result[movement_id] = timezone.localtime(occurred_at).date()
            seen.add(movement_id)
    return result


def sync_quality_events_for_movements(movement_ids=None, *, start: date | None = None, end: date | None = None) -> int:
    """Materializa ROM13 da janela oficial V3, sem culpa automática.

    Importações históricas podem conter meses de ROM13. A fila do coordenador
    começa somente no marco da avaliação V3, evitando transformar histórico já
    encerrado em centenas de decisões manuais.
    """
    activation = evaluation_v3_start_date()
    start = max(start or activation, activation)
    if end is not None and end < activation:
        return 0
    occs = DeliveryOccurrence.objects.filter(source="SSW_ROMANEIO").filter(
        Q(code="13") | Q(description__icontains="ENTREGA PREJUDICADA PELO HORARIO")
    ).exclude(movement_id__isnull=True)
    if movement_ids is not None:
        occs = occs.filter(movement_id__in=list(movement_ids))
    if start:
        occs = occs.filter(Q(occurred_at__date__gte=start) | Q(occurred_at__isnull=True, movement__movement_date__gte=start))
    if end:
        occs = occs.filter(Q(occurred_at__date__lte=end) | Q(occurred_at__isnull=True, movement__movement_date__lte=end))
    occs = list(
        occs.select_related("movement", "movement__driver", "movement__cte", "movement__manifest", "movement__client")
        .order_by("movement_id", "occurred_at", "pk")
    )
    if not occs:
        return 0

    first_by_movement = {}
    for occ in occs:
        first_by_movement.setdefault(occ.movement_id, occ)
    existing = set(
        DriverQualityEvent.objects.filter(movement_id__in=first_by_movement).values_list("movement_id", flat=True)
    )
    movements = [occ.movement for mid, occ in first_by_movement.items() if mid not in existing]
    op_dates = _operation_dates_for_movements(movements)
    new = []
    for movement in movements:
        occ = first_by_movement[movement.pk]
        op_date = op_dates.get(movement.pk) or movement.movement_date
        new.append(DriverQualityEvent(
            movement=movement,
            driver=movement.driver,
            cte=movement.cte,
            manifest=movement.manifest,
            client=movement.client,
            source_occurrence=occ,
            code="13",
            operation_date=op_date,
            status=DriverQualityEvent.Status.PENDING,
        ))
    if not new:
        return 0
    DriverQualityEvent.objects.bulk_create(new, ignore_conflicts=True, batch_size=500)
    invalidate_operational_cache("quality-events-synced")
    return len(new)


def review_quality_event(event: DriverQualityEvent, *, status: str, reviewer, visible_reason: str = "", internal_note: str = ""):
    if status not in {x for x, _ in DriverQualityEvent.Status.choices}:
        raise ValueError("Status de avaliação inválido.")
    visible_reason = (visible_reason or "").strip()
    internal_note = (internal_note or "").strip()
    if status == DriverQualityEvent.Status.DRIVER_RESPONSIBLE and not visible_reason:
        raise ValueError("Informe o motivo visível ao motorista para confirmar a responsabilidade.")

    before = {
        "status": event.status,
        "visible_reason": event.visible_reason,
        "internal_note": event.internal_note,
        "reviewed_by_id": event.reviewed_by_id,
        "reviewed_at": event.reviewed_at.isoformat() if event.reviewed_at else None,
    }
    event.status = status
    event.visible_reason = visible_reason
    event.internal_note = internal_note
    event.reviewed_by = reviewer
    event.reviewed_at = timezone.now()
    event.save(update_fields=["status", "visible_reason", "internal_note", "reviewed_by", "reviewed_at", "updated_at"])
    AuditLog.objects.create(
        user=reviewer,
        action="DRIVER_QUALITY_EVENT_REVIEWED",
        entity="DriverQualityEvent",
        entity_id=str(event.pk),
        before=before,
        after={
            "status": event.status,
            "visible_reason": event.visible_reason,
            "internal_note": event.internal_note,
            "movement_id": event.movement_id,
            "driver_id": event.driver_id,
            "code": event.code,
        },
    )
    invalidate_operational_cache("quality-event-reviewed")
    snapshot_driver_scores(driver_ids=[event.driver_id])
    return event


def reopen_quality_event(event: DriverQualityEvent, *, reviewer, note: str = ""):
    before = {"status": event.status, "visible_reason": event.visible_reason, "internal_note": event.internal_note}
    event.status = DriverQualityEvent.Status.PENDING
    event.visible_reason = ""
    event.internal_note = (note or "").strip()
    event.reviewed_by = reviewer
    event.reviewed_at = timezone.now()
    event.reopened_count += 1
    event.save(update_fields=[
        "status", "visible_reason", "internal_note", "reviewed_by", "reviewed_at", "reopened_count", "updated_at"
    ])
    AuditLog.objects.create(
        user=reviewer,
        action="DRIVER_QUALITY_EVENT_REOPENED",
        entity="DriverQualityEvent",
        entity_id=str(event.pk),
        before=before,
        after={"status": event.status, "internal_note": event.internal_note, "reopened_count": event.reopened_count},
    )
    invalidate_operational_cache("quality-event-reopened")
    snapshot_driver_scores(driver_ids=[event.driver_id])
    return event



def materialize_exact_pickup_opportunities(*, start: date | None = None, end: date | None = None, force: bool = False) -> dict[str, int]:
    """Cria o histórico de Retirada Exata pela rota, mesmo sem abrir o Portal.

    A obrigação nasce da operação real do dia. O Portal deixa de ser requisito
    para provar que o motorista esteve no cliente. Registros continuam por
    comprovante para preservar rastreabilidade, mas a Regularidade agrupa por
    motorista + cliente/parada + data operacional (uma visita = no máximo uma
    obrigação de regularidade).

    Dias já materializados ficam marcados em AuditLog para o startup não
    reconstruir todo o histórico a cada execução. Imports podem usar force=True
    para reprocessar apenas a janela afetada.
    """
    from apps.core.services import manifests_for_operational_date
    from apps.operations.services import build_manifest_cards

    activation = evaluation_v3_start_date()
    today = timezone.localdate()
    start = max(start or activation, activation)
    end = min(end or today, today)
    if end < start:
        return {"days": 0, "created": 0, "responded": 0, "skipped_days": 0}

    marker_action = "EXACT_PICKUP_DAY_MATERIALIZED"
    marked = set()
    if not force:
        marked = {
            value for value in AuditLog.objects.filter(
                action=marker_action, entity="ProofPickupOpportunity",
                entity_id__gte=start.isoformat(), entity_id__lte=end.isoformat(),
            ).values_list("entity_id", flat=True)
        }

    counters = defaultdict(int)
    day = start
    while day <= end:
        day_key = day.isoformat()
        if day_key in marked and day < today:
            counters["skipped_days"] += 1
            day += timedelta(days=1)
            continue

        manifests = list(
            manifests_for_operational_date(day)
            .exclude(status__iexact="CANCELADO")
            .select_related("driver")
            .order_by("pk")
        )
        cards = build_manifest_cards(manifests, persist_available=False, operational_date=day) if manifests else []
        desired = []
        for card in cards:
            manifest = card["manifest"]
            if not manifest.driver_id:
                continue
            for opportunity in card.get("exact", ()):
                desired.append((opportunity.proof_id if hasattr(opportunity, "proof_id") else opportunity.proof.pk,
                                manifest.driver_id, manifest.pk))

        # Idempotência por constraint existente (proof/driver/manifest/date/kind).
        if desired:
            proof_ids = {x[0] for x in desired}
            driver_ids = {x[1] for x in desired}
            manifest_ids = {x[2] for x in desired}
            existing = set(
                ProofPickupOpportunity.objects.filter(
                    proof_id__in=proof_ids, driver_id__in=driver_ids,
                    manifest_id__in=manifest_ids, operation_date=day,
                    kind=ProofPickupOpportunity.Kind.EXACT,
                ).values_list("proof_id", "driver_id", "manifest_id")
            )
            new_rows = [
                ProofPickupOpportunity(
                    proof_id=proof_id, driver_id=driver_id, manifest_id=manifest_id,
                    operation_date=day, kind=ProofPickupOpportunity.Kind.EXACT,
                    status=ProofPickupOpportunity.Status.PRESENTED,
                    source=ProofPickupOpportunity.Source.SYSTEM,
                )
                for proof_id, driver_id, manifest_id in desired
                if (proof_id, driver_id, manifest_id) not in existing
            ]
            if new_rows:
                ProofPickupOpportunity.objects.bulk_create(new_rows, ignore_conflicts=True, batch_size=500)
                counters["created"] += len(new_rows)

            # Se o motorista já respondeu antes do backfill, converte a
            # oportunidade criada pelo sistema para RESPONDED.
            attempts = list(
                ProofPickupAttempt.objects.filter(
                    proof_id__in=proof_ids, driver_id__in=driver_ids,
                    operation_date=day, kind=ProofPickupAttempt.Kind.EXACT,
                ).values("proof_id", "driver_id", "manifest_id", "outcome", "created_at")
            )
            attempt_by_key = {
                (a["proof_id"], a["driver_id"], a["manifest_id"]): a for a in attempts
            }
            to_update = []
            for obj in ProofPickupOpportunity.objects.filter(
                proof_id__in=proof_ids, driver_id__in=driver_ids,
                manifest_id__in=manifest_ids, operation_date=day,
                kind=ProofPickupOpportunity.Kind.EXACT,
                status=ProofPickupOpportunity.Status.PRESENTED,
            ):
                attempt = attempt_by_key.get((obj.proof_id, obj.driver_id, obj.manifest_id))
                if attempt:
                    obj.status = ProofPickupOpportunity.Status.RESPONDED
                    obj.outcome = attempt["outcome"]
                    obj.responded_at = attempt["created_at"]
                    obj.closed_at = attempt["created_at"]
                    to_update.append(obj)
            if to_update:
                ProofPickupOpportunity.objects.bulk_update(
                    to_update, ["status", "outcome", "responded_at", "closed_at", "updated_at"], batch_size=500
                )
                counters["responded"] += len(to_update)

        marker = AuditLog.objects.filter(
            action=marker_action, entity="ProofPickupOpportunity", entity_id=day_key
        ).order_by("pk").first()
        marker_after = {"operation_date": day_key, "force": bool(force)}
        if marker:
            marker.after = marker_after
            marker.save(update_fields=["after"])
        else:
            AuditLog.objects.create(
                user=None, action=marker_action, entity="ProofPickupOpportunity", entity_id=day_key,
                before={}, after=marker_after,
            )
        counters["days"] += 1
        day += timedelta(days=1)

    if counters["created"] or counters["responded"]:
        invalidate_operational_cache("exact-opportunities-materialized")
    return dict(counters)


def present_pickup_opportunities(*, driver: Driver, proofs, kind_by_id: dict[int, str], manifest_by_proof_id: dict[int, object], operation_date: date, source=ProofPickupOpportunity.Source.PORTAL):
    """Persiste apenas o que foi efetivamente exibido no Portal nesta abertura."""
    now = timezone.now()
    created = []
    seen = []
    for proof in proofs:
        manifest = manifest_by_proof_id.get(proof.pk)
        if not manifest:
            continue
        kind = kind_by_id.get(proof.pk, ProofPickupOpportunity.Kind.GOLD)
        obj, was_created = ProofPickupOpportunity.objects.get_or_create(
            proof=proof,
            driver=driver,
            manifest=manifest,
            operation_date=operation_date,
            kind=kind,
            defaults={"source": source, "status": ProofPickupOpportunity.Status.PRESENTED},
        )
        if not was_created and obj.status == ProofPickupOpportunity.Status.PRESENTED:
            obj.last_presented_at = now
            obj.save(update_fields=["last_presented_at", "updated_at"])
        seen.append(obj)
        if was_created:
            created.append(obj)
            AuditLog.objects.create(
                user=None,
                action="PROOF_PICKUP_OPPORTUNITY_PRESENTED",
                entity="ProofPickupOpportunity",
                entity_id=str(obj.pk),
                before={},
                after={
                    "driver_id": driver.pk,
                    "proof_id": proof.pk,
                    "manifest_id": manifest.pk,
                    "operation_date": str(operation_date),
                    "kind": kind,
                    "source": source,
                },
            )
    if created:
        invalidate_operational_cache("pickup-opportunities-presented")
    return seen


def mark_opportunity_responded(*, proof_id: int, driver_id: int, manifest_id: int, operation_date: date, kind: str, outcome: str):
    opportunity = ProofPickupOpportunity.objects.filter(
        proof_id=proof_id,
        driver_id=driver_id,
        manifest_id=manifest_id,
        operation_date=operation_date,
        kind=kind,
    ).first()
    if not opportunity:
        return None
    before = {"status": opportunity.status, "outcome": opportunity.outcome}
    opportunity.status = ProofPickupOpportunity.Status.RESPONDED
    opportunity.outcome = outcome
    opportunity.responded_at = timezone.now()
    opportunity.closed_at = opportunity.responded_at
    opportunity.save(update_fields=["status", "outcome", "responded_at", "closed_at", "updated_at"])
    AuditLog.objects.create(
        user=None,
        action="PROOF_PICKUP_OPPORTUNITY_RESPONDED",
        entity="ProofPickupOpportunity",
        entity_id=str(opportunity.pk),
        before=before,
        after={"status": opportunity.status, "outcome": outcome},
    )
    invalidate_operational_cache("pickup-opportunity-responded")
    return opportunity


def finalize_expired_pickup_opportunities(*, as_of: date | None = None) -> dict[str, int]:
    """Fecha oportunidades de datas operacionais anteriores. EXACT vira omissão; GOLD é neutra."""
    as_of = as_of or timezone.localdate()
    qs = ProofPickupOpportunity.objects.filter(status=ProofPickupOpportunity.Status.PRESENTED, operation_date__lt=as_of)
    exact = list(qs.filter(kind=ProofPickupOpportunity.Kind.EXACT))
    gold = list(qs.filter(kind=ProofPickupOpportunity.Kind.GOLD))
    now = timezone.now()
    if exact:
        for obj in exact:
            obj.status = ProofPickupOpportunity.Status.MISSED
            obj.closed_at = now
            obj.updated_at = now
        ProofPickupOpportunity.objects.bulk_update(exact, ["status", "closed_at", "updated_at"], batch_size=500)
        AuditLog.objects.bulk_create([
            AuditLog(
                user=None, action="PROOF_PICKUP_OPPORTUNITY_MISSED", entity="ProofPickupOpportunity", entity_id=str(obj.pk),
                before={"status": ProofPickupOpportunity.Status.PRESENTED},
                after={"status": ProofPickupOpportunity.Status.MISSED, "driver_id": obj.driver_id, "kind": obj.kind},
            ) for obj in exact
        ], batch_size=500)
    if gold:
        for obj in gold:
            obj.status = ProofPickupOpportunity.Status.EXPIRED_NEUTRAL
            obj.closed_at = now
            obj.updated_at = now
        ProofPickupOpportunity.objects.bulk_update(gold, ["status", "closed_at", "updated_at"], batch_size=500)
    if exact or gold:
        invalidate_operational_cache("pickup-opportunities-finalized")
    return {"missed_exact": len(exact), "expired_gold": len(gold)}



def ensure_actions_activation_date() -> date:
    """Inicializa uma única vez o marco prospectivo da Regularidade V3.

    O objetivo é impedir que ROM34 históricos anteriores à implantação da v0.9.2
    se transformem retroativamente em omissões do motorista.
    """
    from apps.core.models import SystemSettings
    settings_obj = SystemSettings.load()
    if settings_obj.driver_v3_actions_activation_date:
        return settings_obj.driver_v3_actions_activation_date
    activation = V3_ROLLOUT_DATE
    settings_obj.driver_v3_actions_activation_date = activation
    settings_obj.save(update_fields=["driver_v3_actions_activation_date", "updated_at"])
    AuditLog.objects.create(
        user=None,
        action="DRIVER_V3_ACTIONS_ACTIVATED",
        entity="SystemSettings",
        entity_id=str(settings_obj.pk),
        before={"driver_v3_actions_activation_date": None},
        after={"driver_v3_actions_activation_date": activation.isoformat()},
    )
    return activation


def sync_retention_obligations(*, start: date | None = None, end: date | None = None) -> dict[str, int]:
    """Materializa a obrigação de ressalva somente para ROM34 prospectivo.

    ROM34 histórico confirma que houve retenção na tentativa. Se o motorista já
    registrou ProofRetention, a obrigação fica FULFILLED. Caso contrário, ela só
    vira MISSED depois que a data operacional terminou. O status atual do CTRC
    não muda esse fato histórico, mas também não gera dupla penalização.
    """
    from apps.core.models import SystemSettings
    settings_obj = SystemSettings.load()
    activation = settings_obj.driver_v3_actions_activation_date
    if not activation:
        return {"created": 0, "fulfilled": 0, "missed": 0, "pending": 0, "activation_missing": 1}
    today = timezone.localdate()
    start = max(start or activation, activation)
    end = end or today
    occs = list(
        DeliveryOccurrence.objects.filter(
            source="SSW_ROMANEIO", movement__isnull=False,
        ).filter(Q(code="34") | Q(description__icontains="MERCADORIA EM CONFERENCIA NO CLIENTE"))
        .select_related("movement", "movement__driver", "movement__manifest", "movement__cte")
        .order_by("movement_id", "pk")
    )
    if not occs:
        return {"created": 0, "fulfilled": 0, "missed": 0, "pending": 0}
    movements = []
    first_occ = {}
    for occ in occs:
        if occ.movement_id not in first_occ:
            first_occ[occ.movement_id] = occ
            movements.append(occ.movement)
    op_dates = _operation_dates_for_movements(movements)
    valid_movement_ids = [m.pk for m in movements if start <= (op_dates.get(m.pk) or m.movement_date) <= end]
    proof_by_cte = {
        p.cte_id: p for p in RetainedProof.objects.filter(cte_id__in=[m.cte_id for m in movements])
    }
    existing = {
        obj.movement_id: obj for obj in ProofRetentionObligation.objects.filter(movement_id__in=valid_movement_ids)
    }
    retention_evidence = {
        r.proof_id: r for r in ProofRetention.objects.filter(proof_id__in=[p.pk for p in proof_by_cte.values()])
        .select_related("manifest")
    }
    now = timezone.now()
    counters = defaultdict(int)
    changed = []
    for movement in movements:
        op_date = op_dates.get(movement.pk) or movement.movement_date
        if movement.pk not in valid_movement_ids or not (start <= op_date <= end):
            continue
        proof = proof_by_cte.get(movement.cte_id)
        if not proof:
            continue
        evidence = retention_evidence.get(proof.pk)
        fulfilled = bool(
            evidence
            and evidence.driver_id == movement.driver_id
            and (evidence.manifest_id is None or evidence.manifest_id == movement.manifest_id)
        )
        desired = (
            ProofRetentionObligation.Status.FULFILLED if fulfilled
            else ProofRetentionObligation.Status.MISSED if op_date < today
            else ProofRetentionObligation.Status.PENDING
        )
        obj = existing.get(movement.pk)
        if obj is None:
            obj = ProofRetentionObligation.objects.create(
                proof=proof, movement=movement, driver=movement.driver, manifest=movement.manifest,
                operation_date=op_date, status=desired,
                fulfilled_at=(evidence.created_at if fulfilled else None),
                missed_at=(now if desired == ProofRetentionObligation.Status.MISSED else None),
            )
            existing[movement.pk] = obj
            counters["created"] += 1
            counters[desired.lower()] += 1
            AuditLog.objects.create(
                user=None, action="PROOF_RETENTION_OBLIGATION_CREATED", entity="ProofRetentionObligation",
                entity_id=str(obj.pk), before={},
                after={"driver_id": movement.driver_id, "movement_id": movement.pk, "operation_date": op_date.isoformat(), "status": desired},
            )
            continue
        old_status = obj.status
        if obj.driver_id != movement.driver_id:
            obj.driver = movement.driver
        if obj.manifest_id != movement.manifest_id:
            obj.manifest = movement.manifest
        if obj.operation_date != op_date:
            obj.operation_date = op_date
        if obj.status != desired:
            obj.status = desired
            obj.fulfilled_at = evidence.created_at if fulfilled else None
            obj.missed_at = now if desired == ProofRetentionObligation.Status.MISSED else None
            changed.append((obj, old_status))
            counters[desired.lower()] += 1
    if changed:
        ProofRetentionObligation.objects.bulk_update(
            [obj for obj, _ in changed],
            ["driver", "manifest", "operation_date", "status", "fulfilled_at", "missed_at", "updated_at"],
            batch_size=500,
        )
        AuditLog.objects.bulk_create([
            AuditLog(
                user=None, action="PROOF_RETENTION_OBLIGATION_UPDATED", entity="ProofRetentionObligation",
                entity_id=str(obj.pk), before={"status": old}, after={"status": obj.status},
            ) for obj, old in changed
        ], batch_size=500)
    if counters:
        invalidate_operational_cache("retention-obligations-synced")
    return {
        "created": counters["created"],
        "fulfilled": counters["fulfilled"],
        "missed": counters["missed"],
        "pending": counters["pending"],
    }


def regularity_summary(driver_id: int, start: date, end: date) -> dict:
    """Regularidade = ações obrigatórias cumpridas / ações avaliáveis.

    Entram Retiradas Exatas apresentadas e, após o marco prospectivo v0.9.2,
    ressalvas de retenção confirmadas por ROM34. GOLD, dias sem obrigação e
    ROM13/ROM34 como penalização de qualidade nunca entram novamente aqui.
    """
    today = timezone.localdate()
    qs = ProofPickupOpportunity.objects.filter(
        driver_id=driver_id,
        kind=ProofPickupOpportunity.Kind.EXACT,
        operation_date__range=(start, end),
    )
    pickup_fulfilled = qs.filter(status=ProofPickupOpportunity.Status.RESPONDED).count()
    persisted_missed = qs.filter(status=ProofPickupOpportunity.Status.MISSED).count()
    stale_presented = qs.filter(status=ProofPickupOpportunity.Status.PRESENTED, operation_date__lt=today).count()
    pickup_missed = persisted_missed + stale_presented

    retention_qs = ProofRetentionObligation.objects.filter(
        driver_id=driver_id, operation_date__range=(start, end)
    )
    retention_fulfilled = retention_qs.filter(status=ProofRetentionObligation.Status.FULFILLED).count()
    retention_missed = retention_qs.filter(status=ProofRetentionObligation.Status.MISSED).count()

    fulfilled = pickup_fulfilled + retention_fulfilled
    missed = pickup_missed + retention_missed
    evaluated = fulfilled + missed
    score = Decimal("100") if evaluated == 0 else (Decimal(fulfilled) / Decimal(evaluated) * Decimal("100"))
    return {
        "score": score.quantize(Decimal("0.1")),
        "required": evaluated,
        "fulfilled": fulfilled,
        "missed": missed,
        "pickup_fulfilled": pickup_fulfilled,
        "pickup_missed": pickup_missed,
        "retention_fulfilled": retention_fulfilled,
        "retention_missed": retention_missed,
    }


def proof_management_summary(driver_id: int, start: date, end: date) -> dict:
    """Gestão de comprovantes sem punir idade/cliente.

    A idade do documento é mantida como indicador operacional. A nota deste pilar
    usa somente ações de comprovante que podem ser atribuídas ao motorista. Respostas
    neutras corretamente registradas contam como gestão adequada; uma recuperação
    rejeitada é o único desfecho negativo automático desta versão. Omissão de ação
    obrigatória pertence à Regularidade e não é descontada novamente aqui.
    """
    attempts = list(
        ProofPickupAttempt.objects.filter(driver_id=driver_id, operation_date__range=(start, end), kind=ProofPickupAttempt.Kind.EXACT)
        .select_related("submission")
    )
    managed = 0
    failures = 0
    pending = 0
    neutral = 0
    approved = 0
    for attempt in attempts:
        if attempt.outcome in {ProofPickupAttempt.Outcome.NOT_RELEASED, ProofPickupAttempt.Outcome.UNABLE}:
            managed += 1
            neutral += 1
            continue
        if attempt.outcome == ProofPickupAttempt.Outcome.RECOVERED:
            if attempt.submission and attempt.submission.status == ProofRecoverySubmission.Status.APPROVED:
                managed += 1
                approved += 1
            elif attempt.submission and attempt.submission.status == ProofRecoverySubmission.Status.REJECTED:
                failures += 1
            else:
                pending += 1
    evaluated = managed + failures
    score = Decimal("100") if evaluated == 0 else (Decimal(managed) / Decimal(evaluated) * Decimal("100"))
    return {
        "score": score.quantize(Decimal("0.1")),
        "managed": managed,
        "failures": failures,
        "pending": pending,
        "neutral": neutral,
        "approved": approved,
        "evaluated": evaluated,
    }


def quality_summary(driver_id: int, start: date, end: date, *, movement_ids=None) -> dict:
    qs = DriverQualityEvent.objects.filter(driver_id=driver_id, operation_date__range=(start, end))
    if movement_ids is not None:
        qs = qs.filter(movement_id__in=list(movement_ids))
    counts = defaultdict(int)
    for status in qs.values_list("status", flat=True):
        counts[status] += 1
    return {
        "responsible": counts[DriverQualityEvent.Status.DRIVER_RESPONSIBLE],
        "not_responsible": counts[DriverQualityEvent.Status.NOT_RESPONSIBLE],
        "pending": counts[DriverQualityEvent.Status.PENDING],
        "verify": counts[DriverQualityEvent.Status.VERIFY],
        "total_events": sum(counts.values()),
    }


def evaluation_events_for_driver(driver_id: int, start: date, end: date, *, limit=50):
    return list(
        DriverQualityEvent.objects.filter(driver_id=driver_id, operation_date__range=(start, end))
        .select_related("movement", "manifest", "cte", "client", "reviewed_by")
        .order_by("-operation_date", "-pk")[:limit]
    )


def _json_safe(value):
    """Converte Decimal/date/containers para JSON estável sem perder explicação."""
    from datetime import date as _date, datetime as _datetime
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (_date, _datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def snapshot_driver_scores(*, score_date: date | None = None, period_start: date | None = None,
                           period_end: date | None = None, driver_ids=None, force: bool = True) -> int:
    """Persiste fotografia completa da Nota V3 para navegação instantânea.

    O cálculo pesado ocorre em startup/import/worker. As requests leem esta
    fotografia quando o cache está frio. Um lock compartilhado evita dois
    processos reconstruírem o mesmo período simultaneamente.
    """
    from apps.core.services import calculate_driver_metrics
    from .models import DriverScoreSnapshot

    score_date = score_date or timezone.localdate()
    period_end = period_end or score_date
    period_start = period_start or period_end.replace(day=1)
    ids = None
    queryset = None
    if driver_ids is not None:
        ids = list({int(pk) for pk in driver_ids if pk})
        if not ids:
            return 0
        queryset = Driver.objects.filter(pk__in=ids)

    lock = _snapshot_build_lock(period_start, period_end, ids)
    if lock is None:
        # Outro worker já está preparando exatamente esta fotografia.
        return 0
    try:
        metrics = calculate_driver_metrics(
            period_start, period_end, queryset=queryset,
            force_recompute=force, allow_snapshot=False,
        )
        changed = 0
        for metric in metrics:
            payload = {
                "score_breakdown": _json_safe(metric.score_breakdown or {}),
                SNAPSHOT_METRIC_KEY: _metric_to_payload(metric),
            }
            DriverScoreSnapshot.objects.update_or_create(
                driver=metric.driver,
                score_date=score_date,
                period_start=period_start,
                period_end=period_end,
                defaults={
                    "general_score": metric.general_score,
                    "proof_management_score": metric.proof_management_score,
                    "operational_quality_score": metric.operational_quality_score,
                    "regularity_score": metric.regularity_score,
                    "recovery_bonus": metric.recovery_bonus,
                    "attempts": metric.evaluation_attempts,
                    "eligible": metric.eligible,
                    "breakdown": payload,
                },
            )
            changed += 1
        return changed
    finally:
        _release_snapshot_lock(lock)

def score_history_for_driver(driver_id: int, *, limit: int = 14):
    from .models import DriverScoreSnapshot
    return list(
        DriverScoreSnapshot.objects.filter(driver_id=driver_id)
        .order_by("-score_date", "-updated_at")[: max(int(limit or 14), 1)]
    )
