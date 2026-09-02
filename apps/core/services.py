from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from statistics import median
import re
import unicodedata

from django.db.models import Count, Q
from django.utils import timezone

from apps.operations.models import DeliveryMovement, DeliveryOccurrence, Manifest
from apps.proofs.models import RetainedProof
from .models import SystemSettings
from .performance import build_performance_score, percent, sample_confidence


ROUTE_EXIT_CODE = "85"
ROUTE_EXIT_TEXT = "SAIDA PARA ENTREGA"
RETENTION_CODE = "34"
RETENTION_TEXT = "MERCADORIA EM CONFERENCIA NO CLIENTE"
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


def _canonical_manifest_evidence_rows():
    """Retorna ``manifest_id -> (data, classificação)`` sem usar emissão/importação.

    Cada romaneio recebe no máximo UMA data operacional canônica:
    1. primeira SAIDA PARA ENTREGA 85 datada;
    2. se nunca houve 85 datada, primeiro fato ROMANEIO datado;
    3. sem fato: não confirmado/planejamento.

    Essa regra evita que ocorrências posteriores dos CT-es façam o mesmo
    romaneio reaparecer em vários dias do histórico.
    """
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

    # Se o romaneio possui 85 em qualquer data, fatos posteriores não podem
    # recategorizá-lo como INFERRED em outra data.
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
    return result


def operational_manifest_evidence_map(start: date | None = None, end: date | None = None) -> dict[int, dict]:
    """Fonte temporal única consumida por Operação, Dashboard e relatórios."""
    rows = _canonical_manifest_evidence_rows()
    payload = {}
    for manifest_id, (event_date, confidence) in rows.items():
        if start is not None and event_date < start:
            continue
        if end is not None and event_date > end:
            continue
        payload[manifest_id] = {"date": event_date, "confidence": confidence}
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
    """Romaneios observados *agora* como SAIDA PARA ENTREGA.

    Esta fonte serve somente para a Operação do Dia corrente. O CTRC é estado
    consolidado e por isso NÃO reescreve histórico; porém, quando o relatório
    sincronizado hoje informa que um CT-e do romaneio está atualmente em
    ``SAIDA PARA ENTREGA``, a rota não pode continuar aparecendo em
    Planejamento. O dia corrente recebe essa rota como confirmação ao vivo.

    Para datas encerradas, a função sempre retorna vazio e a data continua
    dependendo exclusivamente da trilha ROMANEIO datada/canônica.
    """
    if target_date != timezone.localdate():
        return set()
    live_state = (
        Q(cte__current_status__icontains=ROUTE_EXIT_TEXT)
        | Q(cte__current_status__iexact=ROUTE_EXIT_CODE)
        # Compatibilidade com movimentos recém-importados por versões em que
        # current_status ainda não foi materializado: occurrence_text é aceito
        # somente quando o próprio romaneio foi emitido hoje. Emissão aqui é
        # apenas uma trava de segurança do snapshot ao vivo, nunca uma fonte de
        # data histórica.
        | (
            Q(manifest__date=target_date)
            & (Q(occurrence_text__icontains=ROUTE_EXIT_TEXT) | Q(occurrence_text__iexact=ROUTE_EXIT_CODE))
        )
    )
    return set(
        DeliveryMovement.objects.filter(live_state)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .values_list("manifest_id", flat=True)
        .distinct()
    )


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
    """Romaneios ainda abertos no início de HOJE, nunca para reescrever histórico."""
    if target_date != timezone.localdate():
        return set()

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
    for occurrence in rows:
        latest_by_movement[occurrence.movement_id] = occurrence

    return {
        occurrence.movement.manifest_id
        for occurrence in latest_by_movement.values()
        if occurrence.movement_id and _occurrence_is_route_exit(occurrence)
    }


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
    """Resolve a data histórica da retenção sem usar importação ou emissão.

    Ordem de confiança:
    1. ROM34 datado ligado ao romaneio original;
    2. data canônica da rota quando existe ROM34 sem data;
    3. ``None`` quando a origem temporal não pode ser provada.

    ``RetainedProof.retained_at`` continua sendo mantido por compatibilidade e
    SLA, mas não reescreve sozinho a fotografia diária quando foi inferido por
    legado.
    """
    proofs = list(proofs)
    if not proofs:
        return {}
    cte_ids = {p.cte_id for p in proofs}
    manifest_by_cte = {p.cte_id: p.original_manifest_id for p in proofs if p.original_manifest_id}
    result: dict[int, date | None] = {p.pk: None for p in proofs}

    qs = DeliveryOccurrence.objects.filter(
        cte_id__in=cte_ids,
        movement__isnull=False,
        source="SSW_ROMANEIO",
    ).filter(Q(code=RETENTION_CODE) | Q(description__icontains=RETENTION_TEXT))

    explicit_by_cte: dict[int, date] = {}
    undated_ctes = set()
    for occurrence in qs.select_related("movement").order_by("occurred_at", "pk"):
        expected_manifest = manifest_by_cte.get(occurrence.cte_id)
        if expected_manifest and occurrence.movement.manifest_id != expected_manifest:
            continue
        if occurrence.occurred_at:
            explicit_by_cte.setdefault(occurrence.cte_id, _local_date(occurrence.occurred_at))
        else:
            undated_ctes.add(occurrence.cte_id)

    route_evidence = _canonical_manifest_evidence_rows()
    for proof in proofs:
        if proof.cte_id in explicit_by_cte:
            result[proof.pk] = explicit_by_cte[proof.cte_id]
            continue
        if proof.cte_id in undated_ctes:
            if proof.original_manifest_id in route_evidence:
                result[proof.pk] = route_evidence[proof.original_manifest_id][0]
            # ROM34 existe, mas sem data. Sem rota canônica não há evidência
            # suficiente: não aceitar emissão/previsão persistida em retained_at.
            continue
        # Registros manuais/validados fora do importador podem ter retained_at
        # real. Só aceitamos esse campo quando há diferença material de criação,
        # evitando tratar o instante de importação como data de negócio.
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
    score_mode: str = "SIMULATION"

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


def calculate_driver_metrics(start: date, end: date, queryset=None, include_inactive=False, include_test=False):
    """Métricas V2 por tentativa, com corte temporal explícito.

    Pontos-chave:
    - tentativa = DeliveryMovement (CT-e + romaneio);
    - entrega é atribuída à última tentativa conhecida antes do evento ENTREGUE;
    - ocorrência 13 e retenção da tentativa usam a trilha ROMANEIO;
    - retenção documental usa RetainedProof.original_driver;
    - recuperação usa RetainedProof.recovery_driver, sem sobrescrever a origem;
    - a nota é SIMULAÇÃO auditável; produtividade permanece separada.
    """
    settings = SystemSettings.load()
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
    if not movements:
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
        "weight": Decimal("0"),
        "volumes": 0,
        "freight_ctes": {},
    })
    for m in movements:
        row = data[m.driver_id]
        row["driver"] = m.driver
        row["movements"] += 1
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
    retention_rows = RetainedProof.objects.filter(
        original_driver_id__in=driver_ids,
        retained_at__date__range=(start, end),
    ).exclude(status=RetainedProof.Status.CANCELED).values(
        "original_driver_id", "status", "freight_value", "recovered_at"
    )
    for record in retention_rows:
        stat = retention_stats[record["original_driver_id"]]
        stat["count"] += 1
        # Valor retido é reconstruído no FECHAMENTO do período. Um comprovante
        # recuperado depois de ``end`` ainda estava aberto nessa fotografia e
        # não pode desaparecer retroativamente só porque hoje está RECUPERADO.
        recovered_at = record.get("recovered_at")
        recovered_by_cut = bool(
            recovered_at and timezone.localtime(recovered_at).date() <= end
        )
        if not recovered_by_cut:
            stat["open_value"] += record["freight_value"] or Decimal("0")

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
    asof_proofs = RetainedProof.objects.filter(
        original_driver_id__in=driver_ids,
        retained_at__date__lte=end,
    ).exclude(status=RetainedProof.Status.CANCELED).only(
        "original_driver_id", "retained_at", "recovered_at", "status"
    )
    for proof in asof_proofs:
        recovered_before_cut = bool(proof.recovered_at and timezone.localtime(proof.recovered_at).date() <= end)
        if recovered_before_cut:
            continue
        days = max((end - timezone.localtime(proof.retained_at).date()).days, 0)
        proof_age_stats[proof.original_driver_id].append(days)
        proof_open_count[proof.original_driver_id] += 1
        if days > proof_sla_days:
            proof_overdue_count[proof.original_driver_id] += 1

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
            score=perf.score,
            eligible=attempts >= min_attempts,
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
            performance_score=perf.score,
            score_breakdown=perf.breakdown,
            sample_confidence=sample_confidence(attempts, min_attempts),
        )
        metrics.append(metric)

    # Ranking ajustado por confiança: volume não vira qualidade. Uma amostra
    # pequena puxa a nota para a média da equipe; conforme a evidência cresce,
    # o ranking converge para a qualidade própria do motorista.
    team_quality_mean = (
        sum((m.performance_score for m in metrics), Decimal("0")) / Decimal(len(metrics))
        if metrics else Decimal("0")
    ).quantize(Decimal("0.1"))
    prior_strength = Decimal(max(min_attempts, 1))
    for m in metrics:
        attempts_d = Decimal(max(m.movements, 0))
        factor = attempts_d / (attempts_d + prior_strength) if attempts_d + prior_strength else Decimal("0")
        adjusted = (factor * m.performance_score) + ((Decimal("1") - factor) * team_quality_mean)
        # Bônus pequeno e limitado para recuperação VALIDADA. Recuperar pendência
        # de outro motorista recebe contribuição um pouco maior, mas nunca faz
        # volume financeiro virar qualidade. Máximo: +2,0 pontos.
        bonus = min(Decimal("2.0"), Decimal(m.recovered) * Decimal("0.15") + Decimal(m.opportunistic_recoveries) * Decimal("0.20"))
        m.recovery_bonus = bonus.quantize(Decimal("0.1"))
        m.confidence_factor = (factor * Decimal("100")).quantize(Decimal("0.1"))
        m.team_quality_mean = team_quality_mean
        m.ranking_score = min(Decimal("100"), adjusted + bonus).quantize(Decimal("0.1"))

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

    metrics.sort(key=lambda x: (x.ranking_score, x.performance_score, x.movements), reverse=True)
    return metrics

def with_trends(metrics, previous_metrics):
    previous = {m.driver.pk: m.score for m in previous_metrics}
    for metric in metrics:
        if metric.driver.pk in previous:
            metric.trend = metric.score - previous[metric.driver.pk]
    return metrics
