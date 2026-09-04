from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.cache import versioned_key
from apps.core.services import (
    completed_cte_ids,
    manifests_for_operational_date,
    normalize,
    normalize_identifier,
    operational_date_for_manifest,
    retention_origin_dates,
)
from apps.proofs.models import RetainedProof
from .models import DeliveryMovement, Manifest


@dataclass
class Opportunity:
    proof: RetainedProof
    kind: str  # EXACT | REGION
    reason: str


OPEN_PROOF_STATUSES = [
    RetainedProof.Status.WAITING,
    RetainedProof.Status.AVAILABLE,
]


def _address_exact(movement, proof):
    """Match exato sem queries: todas as relações devem chegar via select_related."""
    if movement.client_id and movement.client_id == proof.client_id:
        if movement.address_id and proof.address_id and movement.address_id == proof.address_id:
            return True, "Mesmo cliente e endereço"
        if movement.address and proof.address:
            cep_m = normalize_identifier(movement.address.postal_code)
            cep_p = normalize_identifier(proof.address.postal_code)
            if cep_m and cep_p and cep_m == cep_p:
                return True, "Mesmo cliente e CEP"
            if movement.address.normalized_address and movement.address.normalized_address == proof.address.normalized_address:
                return True, "Mesmo cliente e endereço normalizado"

    cnpj_m = normalize_identifier(getattr(movement.client, "cnpj", ""))
    cnpj_p = normalize_identifier(getattr(proof.client, "cnpj", ""))
    if cnpj_m and cnpj_p and cnpj_m == cnpj_p:
        return True, "Mesmo CNPJ"
    return False, ""


def _opportunities_for_moves(moves, proofs):
    """Calcula oportunidades em memória usando listas previamente carregadas."""
    exact, regional = {}, {}
    route_regions = {
        (normalize(m.address.city), normalize(m.address.district))
        for m in moves
        if m.address and m.address.district
    }

    # Índice de movimentos por cliente/CNPJ reduz o produto cartesiano comum.
    moves_by_client = defaultdict(list)
    moves_by_cnpj = defaultdict(list)
    for movement in moves:
        if movement.client_id:
            moves_by_client[movement.client_id].append(movement)
        cnpj = normalize_identifier(getattr(movement.client, "cnpj", ""))
        if cnpj:
            moves_by_cnpj[cnpj].append(movement)

    for proof in proofs:
        candidates = list(moves_by_client.get(proof.client_id, ()))
        proof_cnpj = normalize_identifier(getattr(proof.client, "cnpj", ""))
        if proof_cnpj:
            for movement in moves_by_cnpj.get(proof_cnpj, ()):
                if movement not in candidates:
                    candidates.append(movement)
        for movement in candidates:
            ok, reason = _address_exact(movement, proof)
            if ok:
                exact[proof.pk] = Opportunity(proof, "EXACT", reason)
                break
        region = (normalize(proof.address.city), normalize(proof.address.district)) if proof.address else ("", "")
        if proof.pk not in exact and proof.address and region in route_regions and region[1]:
            regional[proof.pk] = Opportunity(
                proof, "REGION", f"Mesma região: {proof.address.district} / {proof.address.city}"
            )
    return list(exact.values()), list(regional.values())


def _open_proofs(*, as_of: date | None = None, actionable_only: bool = True):
    """Comprovantes disponíveis para análise de oportunidade.

    A fotografia histórica usa a mesma origem temporal de domínio (ROM34/rota
    canônica) do Dashboard e da Central. ``retained_at`` não é usado como atalho
    quando pode representar instante de importação.
    """
    qs = RetainedProof.objects.exclude(status=RetainedProof.Status.CANCELED).select_related(
        "client", "address", "cte", "original_manifest"
    )
    if as_of is None:
        if actionable_only:
            qs = qs.filter(status__in=OPEN_PROOF_STATUSES)
        return list(qs)

    rows = list(qs)
    origins = retention_origin_dates(rows)
    result = []
    for proof in rows:
        origin = origins.get(proof.pk)
        if not origin or origin > as_of:
            continue
        recovered_date = timezone.localtime(proof.recovered_at).date() if proof.recovered_at else None
        delivered_date = (
            timezone.localtime(proof.cte.delivered_at).date()
            if proof.cte and proof.cte.delivered_at else None
        )
        # Reconciliação SSW pode ter sido executada hoje para uma entrega que já
        # havia ocorrido antes. No backfill, delivered_at é evidência mais forte
        # do que o timestamp técnico em que o Painel marcou RECUPERADO.
        if (recovered_date and recovered_date <= as_of) or (delivered_date and delivered_date <= as_of):
            continue
        if actionable_only and as_of >= timezone.localdate() and proof.status not in OPEN_PROOF_STATUSES:
            continue
        result.append(proof)
    return result


def _candidate_open_proofs_for_moves(moves, *, as_of: date | None = None):
    """Carrega somente comprovantes que podem casar com a rota atual.

    Antes, cada card de Operação carregava TODO o estoque de comprovantes e só
    depois descartava quase tudo em Python. Para o estado atual podemos limitar
    no banco por cliente/CNPJ/região e preservar exatamente a mesma regra final
    de matching em ``_opportunities_for_moves``. Fotografias históricas mantêm o
    caminho conservador existente, pois dependem da origem temporal da retenção.
    """
    moves = list(moves)
    if not moves:
        return []
    today = timezone.localdate()
    if as_of is not None and as_of < today:
        return _open_proofs(as_of=as_of, actionable_only=True)

    client_ids = {m.client_id for m in moves if m.client_id}
    raw_cnpjs = {str(getattr(m.client, "cnpj", "") or "").strip() for m in moves if getattr(m, "client", None)}
    raw_cnpjs.discard("")
    regions = {
        (str(m.address.city or "").strip(), str(m.address.district or "").strip())
        for m in moves if m.address and m.address.city and m.address.district
    }
    candidate_q = Q(pk__in=[])
    if client_ids:
        candidate_q |= Q(client_id__in=client_ids)
    if raw_cnpjs:
        candidate_q |= Q(client__cnpj__in=raw_cnpjs)
    for city, district in regions:
        candidate_q |= Q(address__city__iexact=city, address__district__iexact=district)

    qs = RetainedProof.objects.filter(status__in=OPEN_PROOF_STATUSES).select_related(
        "client", "address", "cte", "original_manifest"
    )
    if not (client_ids or raw_cnpjs or regions):
        return []
    return list(qs.filter(candidate_q).distinct())


def find_pickup_opportunities(manifest: Manifest, *, moves=None, proofs=None, as_of: date | None = None):
    if moves is None:
        moves = list(manifest.movements.select_related("client", "address", "cte"))
    if proofs is None:
        proofs = _candidate_open_proofs_for_moves(moves, as_of=as_of)
    return _opportunities_for_moves(moves, proofs)


def sync_available_status(exact_proof_ids):
    exact_proof_ids = set(exact_proof_ids)
    with transaction.atomic():
        RetainedProof.objects.filter(status=RetainedProof.Status.AVAILABLE).exclude(
            pk__in=exact_proof_ids
        ).update(status=RetainedProof.Status.WAITING)
        if exact_proof_ids:
            RetainedProof.objects.filter(
                pk__in=exact_proof_ids, status=RetainedProof.Status.WAITING
            ).update(status=RetainedProof.Status.AVAILABLE)


def build_manifest_cards(manifests, persist_available=True, operational_date: date | None = None):
    manifests = list(manifests)
    if not manifests:
        if persist_available:
            sync_available_status(set())
        return []

    manifest_ids = [m.pk for m in manifests]
    moves = list(
        DeliveryMovement.objects.filter(manifest_id__in=manifest_ids)
        .select_related("client", "address", "cte")
        .order_by("manifest_id", "pk")
    )
    moves_by_manifest = defaultdict(list)
    for movement in moves:
        moves_by_manifest[movement.manifest_id].append(movement)

    proofs = _candidate_open_proofs_for_moves(moves, as_of=operational_date)
    delivered_ids = completed_cte_ids({m.cte_id for m in moves}, as_of=operational_date)
    cards = []
    all_exact = set()
    for manifest in manifests:
        route_moves = moves_by_manifest.get(manifest.pk, [])
        exact, regional = _opportunities_for_moves(route_moves, proofs)
        all_exact.update(o.proof.pk for o in exact)
        districts = sorted({m.address.district for m in route_moves if m.address and m.address.district})
        cities = sorted({m.address.city for m in route_moves if m.address and m.address.city})
        cards.append({
            "manifest": manifest,
            "operational_date": operational_date or operational_date_for_manifest(manifest),
            "movements": len(route_moves),
            "delivered": len({m.cte_id for m in route_moves if m.cte_id in delivered_ids}),
            "clients": len({m.client_id for m in route_moves if m.client_id}),
            "weight_kg": sum((m.weight_kg or Decimal("0") for m in route_moves), Decimal("0")),
            "districts": districts[:5],
            "cities": cities[:4],
            "exact": exact,
            "regional": regional,
            "move_objects": route_moves,
        })
    if persist_available:
        sync_available_status(all_exact)
    return cards


def opportunities_summary(cards):
    exact_ids = {o.proof.pk for card in cards for o in card["exact"]}
    regional_ids = {
        o.proof.pk for card in cards for o in card["regional"] if o.proof.pk not in exact_ids
    }
    return exact_ids, regional_ids


def refresh_today_opportunities(target_date=None):
    from django.utils import timezone

    target_date = target_date or timezone.localdate()
    key = versioned_key("today-exact-opportunities", target_date.isoformat())
    cached_ids = cache.get(key)
    if cached_ids is not None:
        # A disponibilidade é um estado derivado. Reaplica a fotografia para se
        # recuperar de restart/edição manual sem refazer o cálculo de matching.
        exact_ids = set(cached_ids)
        sync_available_status(exact_ids)
        return exact_ids

    manifests = list(
        manifests_for_operational_date(target_date)
        .exclude(status__iexact="CANCELADO")
        .only("id")
    )
    if not manifests:
        sync_available_status(set())
        cache.set(key, [], timeout=60)
        return set()
    manifest_ids = [m.pk for m in manifests]
    moves = list(
        DeliveryMovement.objects.filter(manifest_id__in=manifest_ids)
        .exclude(status__iexact="CANCELADO")
        .select_related("client", "address")
    )
    moves_by_manifest = defaultdict(list)
    for movement in moves:
        moves_by_manifest[movement.manifest_id].append(movement)
    proofs = _candidate_open_proofs_for_moves(moves, as_of=target_date)
    exact_ids = set()
    for manifest_id in manifest_ids:
        exact, _ = _opportunities_for_moves(moves_by_manifest.get(manifest_id, []), proofs)
        exact_ids.update(o.proof.pk for o in exact)
    sync_available_status(exact_ids)
    cache.set(key, sorted(exact_ids), timeout=60)
    return exact_ids
