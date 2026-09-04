from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from statistics import median
import re
import unicodedata

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from apps.operations.models import DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof
from .cache import versioned_key
from .models import SystemSettings
from .performance import build_performance_score, build_performance_v3_score, percent, sample_confidence
from .perf import PerfTimer


ROUTE_EXIT_CODE = "85"
ROUTE_EXIT_TEXT = "SAIDA PARA ENTREGA"
RETENTION_CODE = "34"
RETENTION_TEXT = "MERCADORIA EM CONFERENCIA NO CLIENTE"
TIME_WINDOW_FAIL_CODE = "13"
TIME_WINDOW_FAIL_TEXT = "ENTREGA PREJUDICADA PELO HORARIO"
# Carry-over é uma fotografia operacional exclusivamente do dia corrente. Ele
# nunca deve reescrever o histórico de datas já encerradas.
ROUTE_CARRYOVER_DAYS = 3


_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_MULTI_SPACE = re.compile(r"\s+")

@lru_cache(maxsize=32768)
def normalize(value: str | None) -> str:
    raw = (value or "").strip().upper()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = _NON_ALNUM.sub(" ", raw)
    return _MULTI_SPACE.sub(" ", raw).strip()

@lru_cache(maxsize=32768)
def normalize_identifier(value: str | None) -> str:
    """Normaliza CPF/CNPJ/CEP para comparação, ignorando máscara e pontuação."""
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _local_date(value: datetime | None) -> date | None:
    if value is None:
        return None
    if timezone.is_aware(value):
        return timezone.localtime(value).date()
    return value.date()


def _occurrence_event_key(code: str | None, description: str | None) -> tuple[str, str] | None:
    """Chave semântica estável para comparar ROM x CTRC.

    O código SSW é preferido porque é mais forte que texto. Quando o código não
    existe, usamos a descrição normalizada. Essa função nunca mistura CT-es; o
    chamador sempre inclui ``cte_id`` no escopo da comparação.
    """
    code_value = str(code or "").strip()
    if code_value:
        return ("CODE", code_value)
    description_value = normalize(description)
    if description_value:
        return ("DESC", description_value)
    return None


def _movement_is_time_window_closed(movement_id: int, *, closed_ids: set[int] | None = None) -> bool:
    """Código 13 encerra aquela tentativa, não o CT-e."""
    if closed_ids is not None:
        return movement_id in closed_ids
    return DeliveryOccurrence.objects.filter(
        movement_id=movement_id,
        source="SSW_ROMANEIO",
    ).filter(
        Q(code=TIME_WINDOW_FAIL_CODE) | Q(description__icontains=TIME_WINDOW_FAIL_TEXT)
    ).exists()


def route_exit_occurrences():
    """Saídas 85 da trilha ROMANEIO, vinculadas à tentativa real.

    CTRC é estado consolidado do documento e não pode materializar sozinho a
    data histórica de uma rota. O relatório 036 grava o fato da tentativa na
    trilha ROMANEIO; por isso somente ``SSW_ROMANEIO`` participa da linha do
    tempo da rota.
    """
    return DeliveryOccurrence.objects.filter(
        movement__isnull=False,
        source="SSW_ROMANEIO",
    ).filter(Q(code=ROUTE_EXIT_CODE) | Q(description__icontains=ROUTE_EXIT_TEXT))


def route_activity_occurrences():
    """Fatos datados da tentativa/ROMANEIO que podem sustentar inferência.

    Um evento posterior não cria um *novo* dia para o romaneio. Na ausência de
    85, a data canônica é o PRIMEIRO fato datado da trilha ROMANEIO daquela
    tentativa/romaneio. Assim uma entrega/retenção posterior não migra o
    romaneio inteiro para uma data recente.
    """
    return DeliveryOccurrence.objects.filter(
        movement__isnull=False,
        occurred_at__isnull=False,
        source="SSW_ROMANEIO",
    )


def _historical_reconstructed_manifest_evidence_rows(exclude_manifest_ids: set[int] | None = None):
    """Reconstrói datas históricas SOMENTE quando ROM sem data e CTRC datado
    descrevem o mesmo fato de forma unívoca.

    Regras de segurança:
    - ROM continua sendo a prova da tentativa/romaneio;
    - CTRC só fornece a data para um fato ROM que já existe;
    - se o mesmo fato ROM aparece em mais de um movimento do CT-e, não inferimos;
    - se o CTRC possui mais de uma data distinta para o mesmo fato, não inferimos;
    - se um romaneio recebe candidatos de dias diferentes, ele fica ambíguo.

    Essa regra recupera relatórios históricos do 036 em que ``DATA OCORR ROM``
    veio vazia sem voltar a usar emissão/importação como data operacional.
    """
    exclude_manifest_ids = set(exclude_manifest_ids or ())
    rom_rows = list(
        DeliveryOccurrence.objects.filter(
            movement__isnull=False, source="SSW_ROMANEIO"
        ).values(
            "cte_id", "movement_id", "movement__manifest_id",
            "code", "description", "occurred_at"
        )
    )
    if not rom_rows:
        return {}

    # Unicidade do fato ROM dentro do CT-e: inclui ROM datado e sem data, pois
    # a repetição em outra tentativa torna o casamento CTRC->ROM ambíguo.
    movements_by_event: dict[tuple[int, tuple[str, str]], set[int]] = defaultdict(set)
    undated_candidates: list[tuple[int, int, int, tuple[str, str]]] = []
    relevant_ctes = set()
    relevant_events = set()
    for row in rom_rows:
        event_key = _occurrence_event_key(row.get("code"), row.get("description"))
        movement_id = row.get("movement_id")
        manifest_id = row.get("movement__manifest_id")
        cte_id = row.get("cte_id")
        if not event_key or not movement_id or not manifest_id or not cte_id:
            continue
        scoped = (int(cte_id), event_key)
        movements_by_event[scoped].add(int(movement_id))
        if row.get("occurred_at") is None and int(manifest_id) not in exclude_manifest_ids:
            undated_candidates.append((int(cte_id), int(movement_id), int(manifest_id), event_key))
            relevant_ctes.add(int(cte_id))
            relevant_events.add(event_key)

    if not undated_candidates:
        return {}

    ctrc_dates: dict[tuple[int, tuple[str, str]], set[date]] = defaultdict(set)
    ctrc_rows = DeliveryOccurrence.objects.filter(
        cte_id__in=relevant_ctes, source="SSW_CTRC", occurred_at__isnull=False
    ).values("cte_id", "code", "description", "occurred_at")
    for row in ctrc_rows.iterator():
        event_key = _occurrence_event_key(row.get("code"), row.get("description"))
        if event_key not in relevant_events:
            continue
        scoped = (int(row["cte_id"]), event_key)
        event_date = _local_date(row.get("occurred_at"))
        if event_date:
            ctrc_dates[scoped].add(event_date)

    dates_by_manifest: dict[int, set[date]] = defaultdict(set)
    for cte_id, movement_id, manifest_id, event_key in undated_candidates:
        scoped = (cte_id, event_key)
        if len(movements_by_event.get(scoped, ())) != 1:
            continue
        candidate_dates = ctrc_dates.get(scoped, set())
        if len(candidate_dates) != 1:
            continue
        dates_by_manifest[manifest_id].update(candidate_dates)

    return {
        manifest_id: next(iter(candidate_dates))
        for manifest_id, candidate_dates in dates_by_manifest.items()
        if len(candidate_dates) == 1
    }


def _canonical_manifest_evidence_rows():
    """Retorna ``manifest_id -> (data, classificação)`` sem usar importação.

    Cada romaneio recebe no máximo UMA data operacional canônica. Como essa
    reconstrução percorre grande parte do histórico, a fotografia completa é
    materializada uma única vez por versão do cache e reutilizada por Dashboard,
    Operação, Ranking e relatórios. Isso evita reconstruir janeiro→hoje em cada
    clique, sem mudar nenhuma regra temporal homologada.
    """
    key = versioned_key("canonical-manifest-evidence")
    cached = cache.get(key)
    if cached is not None:
        return cached

    from django.db.models import Min

    result: dict[int, tuple[date, str]] = {}
    exits = (
        route_exit_occurrences()
        .filter(occurred_at__isnull=False)
        .values("movement__manifest_id")
        .annotate(first_at=Min("occurred_at"))
    )
    for row in exits.iterator():
        manifest_id = row.get("movement__manifest_id")
        event_date = _local_date(row.get("first_at"))
        if manifest_id and event_date:
            result[int(manifest_id)] = (event_date, "CONFIRMED")

    with_exit = set(result)
    activities = (
        route_activity_occurrences()
        .exclude(movement__manifest_id__in=with_exit)
        .values("movement__manifest_id")
        .annotate(first_at=Min("occurred_at"))
    )
    for row in activities.iterator():
        manifest_id = row.get("movement__manifest_id")
        event_date = _local_date(row.get("first_at"))
        if manifest_id and event_date and int(manifest_id) not in result:
            result[int(manifest_id)] = (event_date, "INFERRED")

    reconstructed = _historical_reconstructed_manifest_evidence_rows(set(result))
    for manifest_id, event_date in reconstructed.items():
        result.setdefault(int(manifest_id), (event_date, "INFERRED"))
    cache.set(key, result, timeout=900)
    return result


def operational_manifest_evidence_map(start: date | None = None, end: date | None = None) -> dict[int, dict]:
    """Fonte temporal única consumida por Operação, Dashboard e relatórios.

    A reconstrução histórica é relativamente cara; o resultado é versionado e
    invalidado por qualquer alteração/importação operacional relevante.
    """
    key = versioned_key("operational-evidence", start or "all", end or "all")
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows = _canonical_manifest_evidence_rows()
    payload = {}
    for manifest_id, (event_date, confidence) in rows.items():
        if start is not None and event_date < start:
            continue
        if end is not None and event_date > end:
            continue
        payload[manifest_id] = {"date": event_date, "confidence": confidence}
    cache.set(key, payload, timeout=300)
    return payload


def operational_manifest_ids(start: date, end: date):
    ids = [
        manifest_id for manifest_id, item in operational_manifest_evidence_map(start, end).items()
        if item["confidence"] == "CONFIRMED"
    ]
    return Manifest.objects.filter(pk__in=ids).values_list("pk", flat=True)


def inferred_manifest_ids(start: date, end: date):
    return {
        manifest_id for manifest_id, item in operational_manifest_evidence_map(start, end).items()
        if item["confidence"] == "INFERRED"
    }


def operational_manifest_classification_map(target_date: date) -> dict[int, str]:
    result = {
        manifest_id: item["confidence"]
        for manifest_id, item in operational_manifest_evidence_map(target_date, target_date).items()
    }
    # Confirmação ao vivo vale apenas para hoje e não cria fato histórico.
    for manifest_id in live_route_manifest_ids(target_date):
        result.setdefault(manifest_id, "CONFIRMED")
    return result


def live_route_manifest_ids(target_date: date):
    """Resolve a tentativa ATUAL dos CT-es em SAIDA PARA ENTREGA.

    O código 85 do CTRC é estado consolidado do CT-e e não pode promover todos
    os romaneios históricos. Para hoje:
    - ROM85 explícito de hoje confirma diretamente a tentativa;
    - CTRC85 sem ROM85 datado escolhe no máximo UMA tentativa elegível por CT-e;
    - qualquer movimento com ROM13 (ENTREGA PREJUDICADA PELO HORARIO) é uma
      tentativa encerrada e jamais reaparece como rota atual;
    - data de emissão é usada apenas como desempate do snapshot AO VIVO, nunca
      como evidência de uma data operacional histórica.
    """
    if target_date != timezone.localdate():
        return set()
    cache_key = versioned_key("live-route-manifests", target_date.isoformat())
    cached = cache.get(cache_key)
    if cached is not None:
        return set(cached)

    explicit_route_rows = route_exit_occurrences().filter(occurred_at__date=target_date).exclude(
        movement__status__iexact="CANCELADO"
    ).exclude(movement__manifest__status__iexact="CANCELADO")
    explicit_today = set(explicit_route_rows.values_list("movement__manifest_id", flat=True).distinct())
    explicit_cte_ids = set(explicit_route_rows.values_list("cte_id", flat=True).distinct())

    # Compatibilidade do snapshot atual: algumas linhas recentes trazem ROM85
    # sem DATA OCORR ROM, mas o próprio movimento do romaneio emitido hoje está
    # materializado como SAIDA PARA ENTREGA. Isso vale só para HOJE.
    same_day_snapshot = (
        DeliveryMovement.objects.filter(manifest__date=target_date)
        .filter(Q(occurrence_text__icontains=ROUTE_EXIT_TEXT) | Q(occurrence_text__iexact=ROUTE_EXIT_CODE))
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
    )
    explicit_today.update(same_day_snapshot.values_list("manifest_id", flat=True).distinct())
    explicit_cte_ids.update(same_day_snapshot.values_list("cte_id", flat=True).distinct())

    current_cte_ids = set(
        DeliveryMovement.objects.filter(
            Q(cte__current_status__icontains=ROUTE_EXIT_TEXT)
            | Q(cte__current_status__iexact=ROUTE_EXIT_CODE)
        )
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .values_list("cte_id", flat=True)
        .distinct()
    )
    current_cte_ids.difference_update(explicit_cte_ids)
    if not current_cte_ids:
        cache.set(cache_key, sorted(explicit_today), timeout=60)
        return explicit_today

    movements = list(
        DeliveryMovement.objects.filter(cte_id__in=current_cte_ids)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .select_related("manifest", "cte")
        .order_by("cte_id", "manifest__date", "manifest_id", "pk")
    )
    movement_ids = {m.pk for m in movements}
    closed_ids = set(
        DeliveryOccurrence.objects.filter(
            movement_id__in=movement_ids, source="SSW_ROMANEIO"
        )
        .filter(Q(code=TIME_WINDOW_FAIL_CODE) | Q(description__icontains=TIME_WINDOW_FAIL_TEXT))
        .values_list("movement_id", flat=True)
    )

    # Se o ROM mais recente da tentativa é 85, ele é a melhor pista de qual
    # movimento representa o snapshot corrente, mesmo quando DATA OCORR ROM veio
    # vazia no relatório 036.
    latest_rom_by_movement = {}
    rom_rows = (
        DeliveryOccurrence.objects.filter(
            movement_id__in=movement_ids, source="SSW_ROMANEIO"
        )
        .order_by("movement_id", "occurred_at", "imported_at", "pk")
    )
    for occurrence in rom_rows.iterator():
        latest_rom_by_movement[occurrence.movement_id] = occurrence

    by_cte = defaultdict(list)
    for movement in movements:
        if movement.pk in closed_ids:
            continue
        by_cte[movement.cte_id].append(movement)

    selected_manifests = set(explicit_today)
    for cte_id, candidates in by_cte.items():
        if not candidates:
            continue
        live_attempts = []
        for movement in candidates:
            latest_rom = latest_rom_by_movement.get(movement.pk)
            latest_is_exit = latest_rom is not None and _occurrence_is_route_exit(latest_rom)
            if not latest_is_exit:
                text = normalize(movement.occurrence_text)
                latest_is_exit = (
                    str(movement.occurrence_text or "").strip() == ROUTE_EXIT_CODE
                    or ROUTE_EXIT_TEXT in text
                )
            if latest_is_exit:
                live_attempts.append(movement)
        pool = live_attempts or candidates
        # Só UMA tentativa por CT-e. O manifest mais recente é apenas desempate
        # do estado atual; não entra na linha do tempo histórica.
        chosen = max(pool, key=lambda m: (m.manifest.date, m.manifest_id, m.pk))
        selected_manifests.add(chosen.manifest_id)

    cache.set(cache_key, sorted(selected_manifests), timeout=60)
    return selected_manifests


def planned_manifests(reference_date: date | None = None, lookback_days: int = 2):
    """Romaneios recentes ainda sem qualquer evidência operacional datada."""
    reference_date = reference_date or timezone.localdate()
    start = reference_date - timedelta(days=max(int(lookback_days), 1))
    with_evidence = set(_canonical_manifest_evidence_rows())
    if reference_date == timezone.localdate():
        with_evidence.update(live_route_manifest_ids(reference_date))
    return (
        Manifest.objects.filter(date__range=(start, reference_date))
        .exclude(pk__in=with_evidence)
        .exclude(status__iexact="CANCELADO")
        .distinct()
    )


def _occurrence_is_route_exit(occurrence) -> bool:
    return (
        str(getattr(occurrence, "code", "") or "").strip() == ROUTE_EXIT_CODE
        or ROUTE_EXIT_TEXT in normalize(getattr(occurrence, "description", ""))
    )


def carryover_manifest_ids(target_date: date):
    """Romaneios ainda abertos no início de HOJE, sem reviver tentativa ROM13."""
    if target_date != timezone.localdate():
        return set()
    cache_key = versioned_key("carryover-manifests", target_date.isoformat())
    cached = cache.get(cache_key)
    if cached is not None:
        return set(cached)

    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(target_date, time.min), tz)
    window_start = day_start - timedelta(days=ROUTE_CARRYOVER_DAYS)

    rows = (
        DeliveryOccurrence.objects.filter(
            movement__isnull=False,
            source="SSW_ROMANEIO",
            occurred_at__gte=window_start,
            occurred_at__lt=day_start,
        )
        .select_related("movement")
        .order_by("movement_id", "occurred_at", "imported_at", "pk")
    )
    latest_by_movement = {}
    movement_ids = set()
    for occurrence in rows:
        latest_by_movement[occurrence.movement_id] = occurrence
        movement_ids.add(occurrence.movement_id)

    closed_ids = set()
    if movement_ids:
        closed_ids = set(
            DeliveryOccurrence.objects.filter(
                movement_id__in=movement_ids, source="SSW_ROMANEIO"
            )
            .filter(Q(code=TIME_WINDOW_FAIL_CODE) | Q(description__icontains=TIME_WINDOW_FAIL_TEXT))
            .values_list("movement_id", flat=True)
        )

    result = {
        occurrence.movement.manifest_id
        for occurrence in latest_by_movement.values()
        if occurrence.movement_id
        and occurrence.movement_id not in closed_ids
        and _occurrence_is_route_exit(occurrence)
    }
    cache.set(cache_key, sorted(result), timeout=60)
    return result


def manifests_for_operational_date(target_date: date):
    """Romaneios do dia segundo a fonte temporal canônica.

    Histórico: somente CONFIRMED/INFERRED na data canônica.
    Hoje: além disso, carry-over ainda aberto no início do dia.
    """
    evidence_ids = set(operational_manifest_evidence_map(target_date, target_date))
    if target_date == timezone.localdate():
        evidence_ids.update(live_route_manifest_ids(target_date))
        evidence_ids.update(carryover_manifest_ids(target_date))
    return Manifest.objects.filter(pk__in=evidence_ids).distinct()


def operational_movements_for_period(start: date, end: date):
    """Movimentos dos romaneios cuja data canônica pertence ao período.

    Não existe fallback por ``movement_date``/emissão/importação. Se não há
    evidência operacional, o movimento continua consultável como "data não
    confirmada" em Entregas Gerais, mas não contamina KPIs históricos.
    """
    manifest_ids = set(operational_manifest_evidence_map(start, end))
    today = timezone.localdate()
    if start <= today <= end:
        manifest_ids.update(live_route_manifest_ids(today))
        manifest_ids.update(carryover_manifest_ids(today))
    return DeliveryMovement.objects.filter(manifest_id__in=manifest_ids).distinct()


def operational_date_map(start: date, end: date) -> dict[int, date]:
    result = {
        manifest_id: item["date"]
        for manifest_id, item in operational_manifest_evidence_map(start, end).items()
    }
    today = timezone.localdate()
    if start <= today <= end:
        for manifest_id in live_route_manifest_ids(today):
            result.setdefault(manifest_id, today)
        for manifest_id in carryover_manifest_ids(today):
            result.setdefault(manifest_id, today)
    return result


def operational_date_for_manifest(manifest: Manifest, preferred_date: date | None = None) -> date:
    evidence = _canonical_manifest_evidence_rows().get(manifest.pk)
    if evidence:
        event_date, _confidence = evidence
        # ``preferred_date`` só prevalece para estado operacional ao vivo do dia
        # corrente (saída atual ou carry-over), nunca para histórico encerrado.
        if preferred_date == timezone.localdate() and (
            manifest.pk in live_route_manifest_ids(preferred_date)
            or manifest.pk in carryover_manifest_ids(preferred_date)
        ):
            return preferred_date
        return event_date
    if preferred_date == timezone.localdate() and manifest.pk in live_route_manifest_ids(preferred_date):
        return preferred_date
    # Compatibilidade visual de planejamento: emissão é apenas referência, nunca
    # evidência operacional. A classificação permanecerá PLANNED.
    return preferred_date or manifest.date


def latest_operational_date() -> date | None:
    dates = [item[0] for item in _canonical_manifest_evidence_rows().values()]
    today = timezone.localdate()
    if live_route_manifest_ids(today):
        dates.append(today)
    return max(dates) if dates else None


def retention_origin_dates(proofs) -> dict[int, date | None]:
    """Resolve a origem temporal da retenção priorizando ROM34 da tentativa.

    Ordem de confiança:
    1. ROM34 datado no romaneio original;
    2. se o ``original_manifest`` legado estiver errado, ROM34 único do CT-e;
    3. ROM34 sem data + data canônica/reconstruída do mesmo romaneio;
    4. ``retained_at`` apenas para registros manuais comprovadamente distintos do
       instante de criação/importação.

    CTRC34 sozinho pode criar uma retenção provisória quando não existe ROM34,
    mas nunca vence um ROM34 existente para escolher motorista/romaneio.
    """
    proofs = list(proofs)
    if not proofs:
        return {}
    cte_ids = {p.cte_id for p in proofs}
    result: dict[int, date | None] = {p.pk: None for p in proofs}

    qs = (
        DeliveryOccurrence.objects.filter(
            cte_id__in=cte_ids,
            movement__isnull=False,
            source="SSW_ROMANEIO",
        )
        .filter(Q(code=RETENTION_CODE) | Q(description__icontains=RETENTION_TEXT))
        .select_related("movement")
        .order_by("cte_id", "occurred_at", "pk")
    )
    rom_by_cte: dict[int, list] = defaultdict(list)
    for occurrence in qs:
        rom_by_cte[occurrence.cte_id].append(occurrence)

    route_evidence = _canonical_manifest_evidence_rows()
    for proof in proofs:
        candidates = rom_by_cte.get(proof.cte_id, [])
        chosen = None
        # O vínculo persistido continua sendo preferido SOMENTE se realmente
        # contém ROM34. Isso evita perpetuar original_manifest errado de versões
        # antigas que escolheram CTRC34 consolidado.
        if proof.original_manifest_id:
            matches = [o for o in candidates if o.movement.manifest_id == proof.original_manifest_id]
            if matches:
                chosen = matches[0]
        if chosen is None:
            manifest_ids = {o.movement.manifest_id for o in candidates}
            if len(manifest_ids) == 1:
                chosen = candidates[0]

        if chosen is not None:
            chosen_manifest = chosen.movement.manifest_id
            explicit_dates = [
                _local_date(o.occurred_at)
                for o in candidates
                if o.movement.manifest_id == chosen_manifest and o.occurred_at
            ]
            explicit_dates = [d for d in explicit_dates if d]
            if explicit_dates:
                result[proof.pk] = min(explicit_dates)
                continue
            if chosen_manifest in route_evidence:
                result[proof.pk] = route_evidence[chosen_manifest][0]
                continue

        # Registro manual/validado fora do importador: aceita retained_at quando
        # ele não coincide com o instante técnico de criação.
        if proof.retained_at and proof.created_at:
            delta = abs((proof.retained_at - proof.created_at).total_seconds())
            if delta > 300:
                result[proof.pk] = _local_date(proof.retained_at)
    return result


def retention_stats_for_date(target_date: date) -> dict[str, int]:
    proofs = list(
        RetainedProof.objects.exclude(status=RetainedProof.Status.CANCELED)
        .select_related("original_manifest")
    )
    origin_dates = retention_origin_dates(proofs)
    selected = [p for p in proofs if origin_dates.get(p.pk) == target_date]
    recovered_later = sum(
        1 for p in selected
        if p.recovered_at and _local_date(p.recovered_at) and _local_date(p.recovered_at) > target_date
    )
    still_open = sum(1 for p in selected if p.recovered_at is None)
    return {
        "retained": len(selected),
        "recovered_later": recovered_later,
        "still_open": still_open,
    }

def parse_period(request, default="month"):
    """Retorna (início, fim, label, modo) a partir dos query params."""
    today = timezone.localdate()
    mode = request.GET.get("period", default)
    start_raw = request.GET.get("start")
    end_raw = request.GET.get("end")
    if start_raw and end_raw:
        try:
            start = date.fromisoformat(start_raw)
            end = date.fromisoformat(end_raw)
            if start > end:
                start, end = end, start
            return start, end, f"{start:%d/%m/%Y} — {end:%d/%m/%Y}", "custom"
        except ValueError:
            pass
    if mode == "today":
        return today, today, today.strftime("%d/%m/%Y"), mode
    if mode == "yesterday":
        day = today - timedelta(days=1)
        return day, day, day.strftime("%d/%m/%Y"), mode
    if mode == "week":
        start = today - timedelta(days=today.weekday())
        return start, today, f"Semana · {start:%d/%m} — {today:%d/%m}", mode
    rolling_days = {"7d": 7, "30d": 30, "60d": 60, "90d": 90}
    if mode in rolling_days:
        days = rolling_days[mode]
        start = today - timedelta(days=days - 1)
        return start, today, f"Últimos {days} dias · {start:%d/%m} — {today:%d/%m}", mode
    if mode == "year":
        start = date(today.year, 1, 1)
        return start, today, str(today.year), mode
    start = date(today.year, today.month, 1)
    month_names = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return start, today, f"{month_names[today.month]} {today.year}", "month"


def previous_period(start: date, end: date):
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    return previous_end - timedelta(days=days - 1), previous_end


def completed_cte_ids(cte_ids=None, *, as_of: date | None = None):
    """CT-es entregues até uma data de corte.

    O parâmetro ``as_of`` evita que uma entrega futura contamine uma visão
    histórica. Ex.: rota em 01/08 entregue em 03/08 não pode aparecer como
    entregue ao consultar a fotografia de 01/08.
    """
    qs = DeliveryOccurrence.objects.filter(
        Q(description__iexact="ENTREGUE") | Q(description__icontains="ENTREGUE")
    ).exclude(description__icontains="NAO ENTREGUE")
    if cte_ids is not None:
        qs = qs.filter(cte_id__in=cte_ids)
    if as_of is not None:
        # Fotografia histórica exige data de negócio comprovada. Ocorrência
        # ENTREGUE sem occurred_at não pode herdar movement_date/emissão apenas
        # para caber no corte, pois isso reescreveria o passado.
        qs = qs.filter(occurred_at__isnull=False, occurred_at__date__lte=as_of)
    return set(qs.values_list("cte_id", flat=True).distinct())


def is_delivery_completed(cte, *, as_of: date | None = None) -> bool:
    return cte.pk in completed_cte_ids({cte.pk}, as_of=as_of)


@dataclass
class DriverMetric:
    driver: object
    movements: int
    manifests: int
    stops: int
    clients: int
    cities: int
    delivered: int
    retained: int
    recovered: int
    pending: int
    weight_kg: Decimal
    volumes: int
    freight: Decimal
    retained_value: Decimal
    operational_index: Decimal = Decimal("0")
    effort_index: Decimal = Decimal("0")
    score: Decimal = Decimal("0")
    eligible: bool = True
    trend: Decimal | None = None
    opportunistic_recoveries: int = 0
    recovered_freight_value: Decimal = Decimal("0")
    recovery_bonus: Decimal = Decimal("0")
    # V2 — qualidade operacional. ``score`` permanece como alias da nota de
    # desempenho SIMULADA para compatibilidade com templates antigos.
    first_attempt_delivered: int = 0
    clean_deliveries: int = 0
    time_window_failures: int = 0
    active_proofs: int = 0
    overdue_proofs: int = 0
    avg_proof_days: Decimal = Decimal("0")
    median_proof_days: Decimal = Decimal("0")
    max_proof_days: int = 0
    success_rate: Decimal = Decimal("0")
    first_attempt_rate: Decimal = Decimal("0")
    clean_delivery_rate: Decimal = Decimal("0")
    retention_rate: Decimal = Decimal("0")
    time_window_rate: Decimal = Decimal("0")
    productivity_score: Decimal = Decimal("0")
    performance_score: Decimal = Decimal("0")
    ranking_score: Decimal = Decimal("0")
    confidence_factor: Decimal = Decimal("0")
    team_quality_mean: Decimal = Decimal("0")
    score_breakdown: dict | None = None
    sample_confidence: str = "LOW"
    score_mode: str = "V3"
    general_score: Decimal = Decimal("0")
    proof_management_score: Decimal = Decimal("0")
    operational_quality_score: Decimal = Decimal("0")
    regularity_score: Decimal = Decimal("100")
    primary_issue_count: int = 0
    exact_recoveries: int = 0
    gold_recoveries: int = 0
    quality_responsible_count: int = 0
    quality_pending_count: int = 0
    quality_not_responsible_count: int = 0
    quality_verify_count: int = 0
    regularity_required: int = 0
    regularity_fulfilled: int = 0
    regularity_missed: int = 0
    regularity_pickup_fulfilled: int = 0
    regularity_pickup_missed: int = 0
    regularity_retention_fulfilled: int = 0
    regularity_retention_missed: int = 0
    proof_management_managed: int = 0
    proof_management_failures: int = 0
    proof_management_pending: int = 0
    # Tentativas que pertencem efetivamente à janela oficial da Avaliação V3.
    # Estatísticas operacionais podem cobrir período maior sem diluir a nota.
    evaluation_attempts: int = 0

    @property
    def attempts(self):
        return self.movements

    @property
    def recovered_proofs(self):
        return self.recovered

    @property
    def execution_pct(self):
        return self.success_rate

    @property
    def weight_t(self):
        return self.weight_kg / Decimal("1000")


def _delivered_occurrence_rows(cte_ids: set[int], end: date):
    if not cte_ids:
        return []
    return list(
        DeliveryOccurrence.objects.filter(cte_id__in=cte_ids, occurred_at__isnull=False)
        .filter(Q(description__iexact="ENTREGUE") | Q(description__icontains="ENTREGUE"))
        .exclude(description__icontains="NAO ENTREGUE")
        .filter(occurred_at__date__lte=end)
        .values_list("cte_id", "occurred_at")
        .order_by("occurred_at", "pk")
    )


def _movement_operational_dates(movements):
    """Resolve datas operacionais em lote sem N+1."""
    movement_ids = [m.pk for m in movements]
    exits = {}
    if movement_ids:
        rows = (
            DeliveryOccurrence.objects.filter(movement_id__in=movement_ids, occurred_at__isnull=False)
            .filter(Q(code=ROUTE_EXIT_CODE) | Q(description__icontains=ROUTE_EXIT_TEXT))
            .values_list("movement_id", "occurred_at")
            .order_by("occurred_at")
        )
        for movement_id, occurred_at in rows:
            if movement_id not in exits:
                exits[movement_id] = timezone.localtime(occurred_at).date()
    return {m.pk: exits.get(m.pk, m.movement_date) for m in movements}


def calculate_driver_metrics(start: date, end: date, queryset=None, include_inactive=False, include_test=False, *, force_recompute=False, allow_snapshot=True):
    """Métricas V3 por tentativa, com corte temporal explícito.

    Pontos-chave:
    - tentativa = DeliveryMovement (CT-e + romaneio);
    - entrega é atribuída à última tentativa conhecida antes do evento ENTREGUE;
    - ocorrência 13 e retenção da tentativa usam a trilha ROMANEIO;
    - retenção documental usa RetainedProof.original_driver;
    - recuperação usa RetainedProof.recovery_driver, sem sobrescrever a origem;
    - a nota é SIMULAÇÃO auditável; produtividade permanece separada.
    """
    timer = PerfTimer("ranking")
    cache_key = None
    if queryset is None and not include_inactive and not include_test:
        cache_key = versioned_key("driver-metrics-v3", start, end)
        if not force_recompute:
            cached_metrics = cache.get(cache_key)
            if cached_metrics is not None:
                timer.mark("cache_hit")
                timer.total()
                return cached_metrics
            if allow_snapshot:
                # Cache invalidado não significa reconstrução de 10–17s na request.
                # A fotografia persistente é a segunda camada e é atualizada no
                # pós-import/validações.
                try:
                    from apps.drivers.evaluation import load_driver_score_snapshots
                    snapshot_metrics = load_driver_score_snapshots(start, end)
                except Exception:
                    snapshot_metrics = None
                if snapshot_metrics is not None:
                    cache.set(cache_key, snapshot_metrics, timeout=300)
                    timer.mark("snapshot_hit")
                    timer.total()
                    return snapshot_metrics

    settings = SystemSettings.load()
    configured_eval_start = getattr(settings, "driver_v3_actions_activation_date", None) or date(2026, 9, 1)
    evaluation_start = max(start, configured_eval_start)
    movements_qs = (
        operational_movements_for_period(start, end)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .select_related("driver", "manifest", "cte", "client", "address")
    )
    if queryset is not None:
        movements_qs = movements_qs.filter(driver__in=queryset)
    # Motoristas de homologação/fictícios nunca entram em métricas oficiais.
    # O perfil individual pode solicitá-los explicitamente para diagnóstico.
    if not include_test:
        movements_qs = movements_qs.filter(driver__is_test=False)
    if not include_inactive:
        movements_qs = movements_qs.filter(driver__active=True)
    movements = list(movements_qs)
    timer.mark("movements")
    if not movements:
        timer.total()
        return []

    cte_ids = {m.cte_id for m in movements}
    period_movement_ids = {m.pk for m in movements}
    driver_ids = {m.driver_id for m in movements}

    # Todas as tentativas conhecidas desses CT-es são necessárias somente para
    # atribuir a entrega à tentativa correta e identificar primeira tentativa.
    all_cte_moves = list(
        DeliveryMovement.objects.filter(cte_id__in=cte_ids)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .select_related("cte")
        .only("id", "cte_id", "driver_id", "manifest_id", "movement_date", "cte__freight_value")
    )
    all_op_dates = _movement_operational_dates(all_cte_moves)
    moves_by_cte = defaultdict(list)
    for movement in all_cte_moves:
        moves_by_cte[movement.cte_id].append(movement)
    for rows in moves_by_cte.values():
        rows.sort(key=lambda m: (all_op_dates.get(m.pk, m.movement_date), m.pk))

    delivery_at = {}
    for cte_id, occurred_at in _delivered_occurrence_rows(cte_ids, end):
        delivery_at.setdefault(cte_id, occurred_at)

    delivered_movement = {}
    for cte_id, occurred_at in delivery_at.items():
        delivery_day = timezone.localtime(occurred_at).date()
        candidates = [m for m in moves_by_cte.get(cte_id, ()) if all_op_dates.get(m.pk, m.movement_date) <= delivery_day]
        if candidates:
            delivered_movement[cte_id] = candidates[-1]

    # Ocorrências de tentativa: apenas ROM. CTRC é estado consolidado do CT-e e
    # não deve transformar uma tentativa antiga em retenção/entrega daquela rota.
    attempt_flags = defaultdict(lambda: {"retention": False, "time_window": False})
    if period_movement_ids:
        occs = DeliveryOccurrence.objects.filter(
            movement_id__in=period_movement_ids,
            source="SSW_ROMANEIO",
        ).only("movement_id", "code", "description")
        for occurrence in occs:
            code = str(occurrence.code or "").strip()
            desc = normalize(occurrence.description)
            if code == "34" or "MERCADORIA EM CONFERENCIA NO CLIENTE" in desc:
                attempt_flags[occurrence.movement_id]["retention"] = True
            if code == "13" or "ENTREGA PREJUDICADA PELO HORARIO" in desc:
                attempt_flags[occurrence.movement_id]["time_window"] = True

    data = defaultdict(lambda: {
        "driver": None,
        "movements": 0,
        "manifests": set(),
        "stops": set(),
        "clients": set(),
        "cities": set(),
        "delivered": 0,
        "first_attempt": 0,
        "clean": 0,
        "retention": 0,
        "time_window": 0,
        "primary_issues": 0,
        "evaluation_attempts": 0,
        "weight": Decimal("0"),
        "volumes": 0,
        "freight_ctes": {},
    })
    for m in movements:
        row = data[m.driver_id]
        row["driver"] = m.driver
        row["movements"] += 1
        movement_op_date = all_op_dates.get(m.pk, m.movement_date)
        if evaluation_start <= movement_op_date <= end:
            row["evaluation_attempts"] += 1
        row["manifests"].add(m.manifest_id)
        if m.client_id:
            row["clients"].add(m.client_id)
        if m.address and m.address.city:
            row["cities"].add(m.address.city)
        row["stops"].add((m.manifest_id, m.client_id, m.address_id))
        row["weight"] += m.weight_kg or Decimal("0")
        row["volumes"] += int(m.volumes or 0)
        row["freight_ctes"][m.cte_id] = m.cte.freight_value or Decimal("0")
        flags = attempt_flags[m.pk]
        if flags["retention"]:
            row["retention"] += 1
        if flags["time_window"]:
            row["time_window"] += 1
        # Evento normalizado: uma tentativa gera no máximo uma causa principal.
        if flags["time_window"] or flags["retention"]:
            row["primary_issues"] += 1

        chosen = delivered_movement.get(m.cte_id)
        if chosen and chosen.pk == m.pk and start <= timezone.localtime(delivery_at[m.cte_id]).date() <= end:
            row["delivered"] += 1
            first_known = moves_by_cte.get(m.cte_id, [m])[0]
            is_first = first_known.pk == m.pk
            if is_first:
                row["first_attempt"] += 1
            if is_first and not flags["retention"] and not flags["time_window"]:
                row["clean"] += 1

    # Eventos de retenção pertencem ao motorista ORIGINAL, independentemente de
    # quem posteriormente recuperou o comprovante.
    retention_stats = defaultdict(lambda: {"count": 0, "open_value": Decimal("0")})
    retention_proofs = list(
        RetainedProof.objects.filter(original_driver_id__in=driver_ids)
        .exclude(status=RetainedProof.Status.CANCELED)
        .select_related("original_manifest")
    )
    retention_origins = retention_origin_dates(retention_proofs)
    for proof in retention_proofs:
        origin = retention_origins.get(proof.pk)
        if not origin or not (start <= origin <= end):
            continue
        stat = retention_stats[proof.original_driver_id]
        stat["count"] += 1
        # Valor retido é reconstruído no FECHAMENTO do período. Um comprovante
        # recuperado depois de ``end`` ainda estava aberto nessa fotografia e
        # não pode desaparecer retroativamente só porque hoje está RECUPERADO.
        recovered_at = proof.recovered_at
        recovered_by_cut = bool(
            recovered_at and timezone.localtime(recovered_at).date() <= end
        )
        if not recovered_by_cut:
            stat["open_value"] += proof.freight_value or Decimal("0")

    recovery_stats = defaultdict(lambda: {"total": 0, "opportunistic": 0, "freight": Decimal("0")})
    for proof in RetainedProof.objects.filter(
        recovery_driver_id__in=driver_ids, recovered_at__date__range=(start, end),
        status=RetainedProof.Status.RECOVERED,
    ).only("recovery_driver_id", "original_driver_id", "freight_value"):
        stat = recovery_stats[proof.recovery_driver_id]
        stat["total"] += 1
        stat["opportunistic"] += int(proof.original_driver_id != proof.recovery_driver_id)
        stat["freight"] += proof.freight_value or Decimal("0")

    # Estoque de comprovantes aberto AO FINAL do período, incluindo retenções mais
    # antigas ainda não solucionadas. Isso mede responsabilidade acumulada sem
    # usar a data de importação.
    proof_age_stats = defaultdict(list)
    proof_open_count = defaultdict(int)
    proof_overdue_count = defaultdict(int)
    proof_sla_days = int(getattr(settings, "proof_sla_days", 7) or 7)
    asof_proofs = retention_proofs
    for proof in asof_proofs:
        origin = retention_origins.get(proof.pk)
        if not origin or origin > end:
            continue
        recovered_before_cut = bool(proof.recovered_at and timezone.localtime(proof.recovered_at).date() <= end)
        if recovered_before_cut:
            continue
        days = max((end - origin).days, 0)
        proof_age_stats[proof.original_driver_id].append(days)
        proof_open_count[proof.original_driver_id] += 1
        if days > proof_sla_days:
            proof_overdue_count[proof.original_driver_id] += 1

    # V3 auditável. Qualidade usa somente ROM13 validado pelo coordenador;
    # Regularidade usa obrigações EXACT efetivamente apresentadas; Gestão de
    # comprovantes não usa idade do documento como culpa automática.
    from apps.drivers.models import DriverQualityEvent
    from apps.proofs.models import (
        ProofPickupAttempt, ProofPickupOpportunity, ProofRecoverySubmission, ProofRetentionObligation
    )

    quality_stats = defaultdict(lambda: {"responsible": 0, "pending": 0, "not_responsible": 0, "verify": 0})
    if period_movement_ids:
        quality_rows = (
            DriverQualityEvent.objects.filter(
                movement_id__in=period_movement_ids, driver_id__in=driver_ids,
                operation_date__range=(evaluation_start, end),
            )
            .values("driver_id", "status")
            .annotate(total=Count("id"))
        )
        for row in quality_rows:
            bucket = quality_stats[row["driver_id"]]
            status = row["status"]
            total = int(row["total"] or 0)
            if status == DriverQualityEvent.Status.DRIVER_RESPONSIBLE:
                bucket["responsible"] += total
            elif status == DriverQualityEvent.Status.NOT_RESPONSIBLE:
                bucket["not_responsible"] += total
            elif status == DriverQualityEvent.Status.VERIFY:
                bucket["verify"] += total
            else:
                bucket["pending"] += total

    regularity_stats = defaultdict(lambda: {
        "fulfilled": 0, "missed": 0,
        "pickup_fulfilled": 0, "pickup_missed": 0,
        "retention_fulfilled": 0, "retention_missed": 0,
    })
    today = timezone.localdate()
    # A Regularidade é uma janela recente configurável que termina no mesmo
    # corte temporal da avaliação. Ela nunca usa dias sem obrigação no denominador.
    regularity_window_days = max(int(getattr(settings, "driver_v3_regularity_window_days", 30) or 30), 1)
    regularity_start = max(evaluation_start, end - timedelta(days=regularity_window_days - 1))
    # Regularidade da Retirada Exata é por PARADA/DIA, não por comprovante.
    # Quatro comprovantes no mesmo cliente visitado no mesmo dia representam
    # uma obrigação de manifestação, nunca quatro penalizações.
    opportunity_rows = list(ProofPickupOpportunity.objects.filter(
        driver_id__in=driver_ids, kind=ProofPickupOpportunity.Kind.EXACT,
        operation_date__range=(regularity_start, end)
    ).values_list("driver_id", "proof__client_id", "operation_date", "status", "proof_id", "outcome"))

    attempt_map = {}
    if opportunity_rows:
        opp_proof_ids = {row[4] for row in opportunity_rows}
        for row in ProofPickupAttempt.objects.filter(
            driver_id__in=driver_ids, proof_id__in=opp_proof_ids,
            kind=ProofPickupAttempt.Kind.EXACT, operation_date__range=(regularity_start, end),
        ).select_related("submission").values_list(
            "driver_id", "proof_id", "operation_date", "outcome", "submission__status"
        ):
            attempt_map[(row[0], row[1], row[2])] = (row[3], row[4])

    stop_states = defaultdict(list)
    for driver_id, client_id, operation_date, status, proof_id, outcome in opportunity_rows:
        state = "PENDING"
        attempt = attempt_map.get((driver_id, proof_id, operation_date))
        if status == ProofPickupOpportunity.Status.RESPONDED:
            attempt_outcome, submission_status = attempt or (outcome, None)
            if attempt_outcome in {ProofPickupAttempt.Outcome.NOT_RELEASED, ProofPickupAttempt.Outcome.UNABLE}:
                state = "FULFILLED"
            elif attempt_outcome == ProofPickupAttempt.Outcome.RECOVERED:
                if submission_status == ProofRecoverySubmission.Status.APPROVED:
                    state = "FULFILLED"
                elif submission_status == ProofRecoverySubmission.Status.REJECTED:
                    state = "MISSED"
                else:
                    # Motorista se manifestou; enquanto a evidência aguarda
                    # coordenador, a obrigação não pode virar penalização.
                    state = "PENDING"
            else:
                state = "FULFILLED"
        elif status == ProofPickupOpportunity.Status.MISSED or (
            status == ProofPickupOpportunity.Status.PRESENTED and operation_date < today
        ):
            state = "MISSED"
        elif status in {ProofPickupOpportunity.Status.CLOSED, ProofPickupOpportunity.Status.EXPIRED_NEUTRAL}:
            state = "NEUTRAL"
        stop_states[(driver_id, client_id, operation_date)].append(state)

    for (driver_id, _client_id, _operation_date), states in stop_states.items():
        bucket = regularity_stats[driver_id]
        # Qualquer manifestação válida na parada cumpre a obrigação de
        # regularidade. Se só existe evidência pendente, aguarda decisão.
        if "FULFILLED" in states:
            bucket["fulfilled"] += 1
            bucket["pickup_fulfilled"] += 1
        elif "PENDING" in states:
            continue
        elif "MISSED" in states:
            bucket["missed"] += 1
            bucket["pickup_missed"] += 1

    # A ressalva de retenção só entra na Regularidade quando existe uma obrigação
    # prospectiva materializada. ROM34 histórico anterior ao marco de ativação não
    # é convertido retroativamente em falha do motorista.
    retention_obligation_rows = ProofRetentionObligation.objects.filter(
        driver_id__in=driver_ids, operation_date__range=(regularity_start, end)
    ).values_list("driver_id", "status", "operation_date")
    for driver_id, status, operation_date in retention_obligation_rows:
        bucket = regularity_stats[driver_id]
        if status == ProofRetentionObligation.Status.FULFILLED:
            bucket["fulfilled"] += 1
            bucket["retention_fulfilled"] += 1
        elif status == ProofRetentionObligation.Status.MISSED or (
            status == ProofRetentionObligation.Status.PENDING and operation_date < today
        ):
            bucket["missed"] += 1
            bucket["retention_missed"] += 1

    proof_management_stats = defaultdict(lambda: {"managed": 0, "failures": 0, "pending": 0})
    pickup_recovery_stats = defaultdict(lambda: {"exact": 0, "gold": 0})
    proof_attempts = ProofPickupAttempt.objects.filter(
        driver_id__in=driver_ids, operation_date__range=(evaluation_start, end)
    ).select_related("submission").only("driver_id", "kind", "outcome", "submission__status")
    for attempt in proof_attempts:
        if attempt.outcome == ProofPickupAttempt.Outcome.RECOVERED:
            if attempt.submission and attempt.submission.status == ProofRecoverySubmission.Status.APPROVED:
                if attempt.kind == ProofPickupAttempt.Kind.GOLD:
                    pickup_recovery_stats[attempt.driver_id]["gold"] += 1
                else:
                    pickup_recovery_stats[attempt.driver_id]["exact"] += 1
                    proof_management_stats[attempt.driver_id]["managed"] += 1
            elif attempt.submission and attempt.submission.status == ProofRecoverySubmission.Status.REJECTED:
                if attempt.kind == ProofPickupAttempt.Kind.EXACT:
                    proof_management_stats[attempt.driver_id]["failures"] += 1
            elif attempt.kind == ProofPickupAttempt.Kind.EXACT:
                proof_management_stats[attempt.driver_id]["pending"] += 1
        elif attempt.kind == ProofPickupAttempt.Kind.EXACT and attempt.outcome in {
            ProofPickupAttempt.Outcome.NOT_RELEASED, ProofPickupAttempt.Outcome.UNABLE
        }:
            # Cliente não liberou / tentativa impossibilitada com manifestação são
            # gestão correta e neutra; não se transformam em punição pelo tempo.
            proof_management_stats[attempt.driver_id]["managed"] += 1

    timer.mark("events")
    metrics = []
    min_attempts = int(getattr(settings, "driver_rank_min_attempts", settings.minimum_sample) or settings.minimum_sample)
    weights = {
        "delivery": getattr(settings, "driver_score_delivery_weight", Decimal("35")),
        "clean": getattr(settings, "driver_score_clean_weight", Decimal("20")),
        "retention": getattr(settings, "driver_score_retention_weight", Decimal("20")),
        "time_window": getattr(settings, "driver_score_time_window_weight", Decimal("15")),
        "proofs": getattr(settings, "driver_score_proof_weight", Decimal("10")),
        "recovery": getattr(settings, "driver_score_recovery_weight", Decimal("0")),
    }
    for driver_id, row in data.items():
        attempts = row["movements"]
        evaluation_attempts = row["evaluation_attempts"]
        rs = retention_stats[driver_id]
        delivered = row["delivered"]
        retention_count = row["retention"]
        success_rate = percent(delivered, attempts)
        first_rate = percent(row["first_attempt"], delivered)
        clean_rate = percent(row["clean"], attempts)
        retention_rate = percent(retention_count, attempts)
        time_rate = percent(row["time_window"], attempts)
        open_proofs = proof_open_count[driver_id]
        overdue = proof_overdue_count[driver_id]
        overdue_rate = percent(overdue, open_proofs) if open_proofs else Decimal("0")
        recovery = recovery_stats[driver_id]
        recoveries = recovery["total"]
        opportunistic_recoveries = recovery["opportunistic"]
        recovery_rate = percent(recoveries, attempts)
        perf = build_performance_score(
            success_rate=success_rate,
            clean_rate=clean_rate,
            retention_rate=retention_rate,
            time_window_rate=time_rate,
            overdue_proof_rate=overdue_rate,
            recovery_rate=recovery_rate,
            weights=weights,
        )
        qstats = quality_stats[driver_id]
        quality_failure_rate = percent(qstats["responsible"], evaluation_attempts) if evaluation_attempts else Decimal("0")
        rstats = regularity_stats[driver_id]
        regularity_required = rstats["fulfilled"] + rstats["missed"]
        regularity_score = percent(rstats["fulfilled"], regularity_required) if regularity_required else Decimal("100")
        pmstats = proof_management_stats[driver_id]
        proof_management_evaluated = pmstats["managed"] + pmstats["failures"]
        proof_management_score = percent(pmstats["managed"], proof_management_evaluated) if proof_management_evaluated else Decimal("100")
        pickup_stats = pickup_recovery_stats[driver_id]
        v3 = build_performance_v3_score(
            success_rate=success_rate,
            primary_issue_rate=quality_failure_rate,
            quality_failure_rate=quality_failure_rate,
            overdue_proof_rate=overdue_rate,
            proof_management_score=proof_management_score,
            exact_recoveries=pickup_stats["exact"],
            gold_recoveries=pickup_stats["gold"],
            regularity_score=regularity_score,
            weights={
                "proofs": getattr(settings, "driver_v3_proofs_weight", Decimal("50")),
                "quality": getattr(settings, "driver_v3_quality_weight", Decimal("35")),
                "regularity": getattr(settings, "driver_v3_regularity_weight", Decimal("15")),
            },
            exact_bonus=getattr(settings, "driver_v3_exact_recovery_bonus", Decimal("0.30")),
            gold_bonus=getattr(settings, "driver_v3_gold_recovery_bonus", Decimal("0.90")),
            bonus_cap=getattr(settings, "driver_v3_bonus_cap", Decimal("5.00")),
        )
        ages = proof_age_stats[driver_id]
        avg_days = (Decimal(sum(ages)) / Decimal(len(ages))).quantize(Decimal("0.1")) if ages else Decimal("0")
        med_days = Decimal(str(median(ages))).quantize(Decimal("0.1")) if ages else Decimal("0")
        metric = DriverMetric(
            driver=row["driver"],
            movements=attempts,
            manifests=len(row["manifests"]),
            stops=len(row["stops"]),
            clients=len(row["clients"]),
            cities=len(row["cities"]),
            delivered=delivered,
            retained=retention_count,
            recovered=recoveries,
            pending=max(attempts - delivered, 0),
            opportunistic_recoveries=opportunistic_recoveries,
            recovered_freight_value=recovery["freight"],
            weight_kg=row["weight"],
            volumes=row["volumes"],
            freight=sum(row["freight_ctes"].values(), Decimal("0")),
            retained_value=rs["open_value"],
            operational_index=success_rate / Decimal("100"),
            score=v3.score,
            eligible=evaluation_attempts >= min_attempts,
            first_attempt_delivered=row["first_attempt"],
            clean_deliveries=row["clean"],
            time_window_failures=row["time_window"],
            active_proofs=open_proofs,
            overdue_proofs=overdue,
            avg_proof_days=avg_days,
            median_proof_days=med_days,
            max_proof_days=max(ages, default=0),
            success_rate=success_rate,
            first_attempt_rate=first_rate,
            clean_delivery_rate=clean_rate,
            retention_rate=retention_rate,
            time_window_rate=time_rate,
            performance_score=v3.score,
            ranking_score=v3.score,
            general_score=v3.score,
            proof_management_score=v3.components["proofs"],
            operational_quality_score=v3.components["quality"],
            regularity_score=v3.components["regularity"],
            primary_issue_count=qstats["responsible"],
            exact_recoveries=pickup_stats["exact"],
            gold_recoveries=pickup_stats["gold"],
            quality_responsible_count=qstats["responsible"],
            quality_pending_count=qstats["pending"],
            quality_not_responsible_count=qstats["not_responsible"],
            quality_verify_count=qstats["verify"],
            regularity_required=regularity_required,
            regularity_fulfilled=rstats["fulfilled"],
            regularity_missed=rstats["missed"],
            regularity_pickup_fulfilled=rstats["pickup_fulfilled"],
            regularity_pickup_missed=rstats["pickup_missed"],
            regularity_retention_fulfilled=rstats["retention_fulfilled"],
            regularity_retention_missed=rstats["retention_missed"],
            proof_management_managed=pmstats["managed"],
            proof_management_failures=pmstats["failures"],
            proof_management_pending=pmstats["pending"],
            score_breakdown=v3.breakdown,
            sample_confidence=sample_confidence(evaluation_attempts, min_attempts),
            evaluation_attempts=evaluation_attempts,
        )
        metrics.append(metric)

    # V3: a Nota Geral é a nota oficial. Confiança/amostra permanece informação
    # explicativa e elegibilidade do ranking, sem transformar volume em qualidade.
    team_quality_mean = (
        sum((m.general_score for m in metrics), Decimal("0")) / Decimal(len(metrics))
        if metrics else Decimal("0")
    ).quantize(Decimal("0.1"))
    for m in metrics:
        m.team_quality_mean = team_quality_mean
        m.confidence_factor = Decimal("100") if m.eligible else (Decimal(m.evaluation_attempts) / Decimal(max(min_attempts, 1)) * Decimal("100")).quantize(Decimal("0.1"))
        m.recovery_bonus = max(Decimal("0"), m.general_score - (
            (m.proof_management_score * getattr(settings, "driver_v3_proofs_weight", Decimal("50"))
             + m.operational_quality_score * getattr(settings, "driver_v3_quality_weight", Decimal("35"))
             + m.regularity_score * getattr(settings, "driver_v3_regularity_weight", Decimal("15")))
            / (getattr(settings, "driver_v3_proofs_weight", Decimal("50")) + getattr(settings, "driver_v3_quality_weight", Decimal("35")) + getattr(settings, "driver_v3_regularity_weight", Decimal("15")) or Decimal("100"))
        )).quantize(Decimal("0.1"))

    # Produtividade relativa à própria amostra, separada da qualidade.
    max_mov = max((m.movements for m in metrics), default=1) or 1
    max_stops = max((m.stops for m in metrics), default=1) or 1
    max_manifests = max((m.manifests for m in metrics), default=1) or 1
    max_weight = max((m.weight_kg for m in metrics), default=Decimal("1")) or Decimal("1")
    ew_total = (
        settings.effort_movements_weight
        + settings.effort_stops_weight
        + settings.effort_manifests_weight
        + settings.effort_weight_kg_weight
    ) or Decimal("100")
    for m in metrics:
        effort = (
            (Decimal(m.movements) / Decimal(max_mov)) * settings.effort_movements_weight
            + (Decimal(m.stops) / Decimal(max_stops)) * settings.effort_stops_weight
            + (Decimal(m.manifests) / Decimal(max_manifests)) * settings.effort_manifests_weight
            + (m.weight_kg / Decimal(max_weight)) * settings.effort_weight_kg_weight
        ) / ew_total
        m.effort_index = effort
        m.productivity_score = (effort * Decimal("100")).quantize(Decimal("0.1"))

    # Classificação oficial prioriza amostra elegível; volume bruto nunca vira
    # bônus de nota, apenas estabiliza a confiança da amostra.
    metrics.sort(key=lambda x: (x.eligible, x.ranking_score, x.performance_score, x.movements), reverse=True)
    if cache_key:
        cache.set(cache_key, metrics, timeout=300)
    timer.total()
    return metrics

def with_trends(metrics, previous_metrics):
    previous = {m.driver.pk: m.score for m in previous_metrics}
    for metric in metrics:
        if metric.driver.pk in previous:
            metric.trend = metric.score - previous[metric.driver.pk]
    return metrics
