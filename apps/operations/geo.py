from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
import unicodedata
from typing import Iterable
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q

from apps.core.services import operational_movements_for_period
from apps.proofs.models import RetainedProof
from .models import DeliveryMovement, DeliveryOccurrence


RETENTION_CODE = "34"
RETENTION_TEXT = "MERCADORIA EM CONFERENCIA NO CLIENTE"
TIME_WINDOW_CODE = "13"
TIME_WINDOW_TEXT = "ENTREGA PREJUDICADA PELO HORARIO"
DELIVERED_CODE = "1"
DELIVERED_TEXT = "ENTREGUE"
ROM_SOURCE = "SSW_ROMANEIO"

OPEN_PROOF_STATUSES = {
    RetainedProof.Status.WAITING,
    RetainedProof.Status.AVAILABLE,
    RetainedProof.Status.RECOVERING,
    RetainedProof.Status.AWAITING_VALIDATION,
}

# Providers são geográficos, nunca por filial. Qualquer deployment/unidade usa a
# mesma engine; novos municípios ganham nível BAIRRO apenas quando existir uma
# fonte confiável cadastrada aqui.
NEIGHBORHOOD_GEOMETRY_PROVIDERS = {
    ("PA", "BELEM"): {
        "kind": "geojson",
        "url": "https://raw.githubusercontent.com/samuel-c-santos/geovisor-belem/refs/heads/master/data/bairros.geojson",
        "feature_name_properties": ["BAI_NM", "Name", "name"],
        "source_label": "GeoVisor Belém / bairros.geojson",
    },
}

MUNICIPALITY_MESH_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{state}"
    "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio"
)
MUNICIPALITY_LOCALITIES_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{state}/municipios"
)

GEO_DOMINANT_CITY_THRESHOLD = float(getattr(settings, "GEO_DOMINANT_CITY_THRESHOLD", 0.80))
GEO_ALERT_MIN_SAMPLE = int(getattr(settings, "GEO_ALERT_MIN_SAMPLE", 10))
GEO_OUTLIER_DOMINANCE_THRESHOLD = float(getattr(settings, "GEO_OUTLIER_DOMINANCE_THRESHOLD", 0.70))
GEO_OUTLIER_MIN_SHARE = float(getattr(settings, "GEO_OUTLIER_MIN_SHARE", 0.02))

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_MULTI_SPACE = re.compile(r"\s+")

# Correções conservadoras. Chave sempre contextualizada por UF/cidade.
NEIGHBORHOOD_ALIASES = {
    ("PA", "ANANINDEUA", "40 HORAS COQUEIRO"): "QUARENTA HORAS",
    ("PA", "ANANINDEUA", "40 HORAS"): "QUARENTA HORAS",
    # Variações reais observadas no relatório 036. O polígono oficial usa TAPANA.
    ("PA", "BELEM", "TAPANA ICOARACI"): "TAPANA",
    ("PA", "BELEM", "TAPANA COARACI"): "TAPANA",
    ("PA", "BELEM", "ICOARACI TAPANA"): "TAPANA",
}


@dataclass(frozen=True)
class GeoMetricDefinition:
    key: str
    label: str
    format: str
    higher_is_better: bool
    palette: str


METRICS: dict[str, GeoMetricDefinition] = {
    "delivered": GeoMetricDefinition("delivered", "Entregas", "integer", True, "positive"),
    "retentions": GeoMetricDefinition("retentions", "Retenções", "integer", False, "negative"),
    "retention_rate": GeoMetricDefinition("retention_rate", "Taxa de retenção", "percent", False, "negative"),
    "time_window_failures": GeoMetricDefinition("time_window_failures", "Horário", "integer", False, "negative"),
    "time_window_rate": GeoMetricDefinition("time_window_rate", "Taxa de horário", "percent", False, "negative"),
    "active_proofs": GeoMetricDefinition("active_proofs", "Comprovantes retidos", "integer", False, "negative"),
    "clean_deliveries": GeoMetricDefinition("clean_deliveries", "Entregas limpas", "integer", True, "positive"),
    "clean_delivery_rate": GeoMetricDefinition("clean_delivery_rate", "Taxa de entrega limpa", "percent", True, "positive"),
    "weight_kg": GeoMetricDefinition("weight_kg", "Peso", "weight", True, "positive"),
    "clients": GeoMetricDefinition("clients", "Clientes", "integer", True, "positive"),
}


def normalize_geo(value: str | None) -> str:
    raw = (value or "").strip().upper()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = _NON_ALNUM.sub(" ", raw)
    return _MULTI_SPACE.sub(" ", raw).strip()


def display_geo(value: str | None) -> str:
    raw = (value or "").strip()
    return raw if raw else "Não informado"


def normalize_state(value: str | None) -> str:
    value = normalize_geo(value)
    return value[:2] if len(value) >= 2 else value


def normalize_city(value: str | None) -> str:
    return normalize_geo(value)


def normalize_neighborhood(value: str | None, *, state: str = "", city: str = "") -> str:
    state_n = normalize_state(state)
    city_n = normalize_city(city)
    district = normalize_geo(value)
    return NEIGHBORHOOD_ALIASES.get((state_n, city_n, district), district)


def active_branch() -> str:
    return str(getattr(settings, "SSW_ROBOT_UNIT", "BEL") or "BEL").strip().upper()


def validate_branch(branch: str | None) -> str:
    requested = str(branch or active_branch()).strip().upper()
    current = active_branch()
    # A baseline v0.3.0.10 ainda não armazena filial por movimento. Portanto a
    # V1 suporta qualquer unidade como deployment ativo, mas não mistura unidades
    # em uma única base. Rejeitar outra filial é mais seguro do que mentir dados.
    if requested != current:
        raise ValueError(
            f"A base ativa pertence à unidade {current}. A unidade {requested} exige "
            "um deployment/base com SSW_ROBOT_UNIT correspondente nesta V1."
        )
    return requested


def neighborhood_provider(state: str, city: str):
    return NEIGHBORHOOD_GEOMETRY_PROVIDERS.get((normalize_state(state), normalize_city(city)))


def municipality_geometry_urls(states: Iterable[str]) -> list[str]:
    return [MUNICIPALITY_MESH_URL.format(state=s) for s in sorted({normalize_state(x) for x in states if normalize_state(x)})]


def municipality_locality_sources(states: Iterable[str]) -> list[dict[str, str]]:
    return [
        {"state": state, "url": MUNICIPALITY_LOCALITIES_URL.format(state=state)}
        for state in sorted({normalize_state(x) for x in states if normalize_state(x)})
    ]


def _is_delivered(code: str | None, description: str | None) -> bool:
    code_n = normalize_geo(code)
    desc = normalize_geo(description)
    return code_n == DELIVERED_CODE or (DELIVERED_TEXT in desc and "NAO ENTREGUE" not in desc)


def _is_retention(code: str | None, description: str | None) -> bool:
    return normalize_geo(code) == RETENTION_CODE or RETENTION_TEXT in normalize_geo(description)


def _is_time_window(code: str | None, description: str | None) -> bool:
    return normalize_geo(code) == TIME_WINDOW_CODE or TIME_WINDOW_TEXT in normalize_geo(description)


def _region_key(movement: DeliveryMovement, level: str, *, parent_state: str = "", parent_city: str = ""):
    address = movement.address
    if not address:
        return None
    state = normalize_state(address.state)
    city = normalize_city(address.city)
    if not state or not city:
        return None
    if level == "municipality":
        return state, city
    if level == "neighborhood":
        if parent_state and state != normalize_state(parent_state):
            return None
        if parent_city and city != normalize_city(parent_city):
            return None
        district = normalize_neighborhood(address.district, state=state, city=city)
        if not district:
            return None
        return state, city, district
    raise ValueError(f"Nível geográfico inválido: {level}")


def _movement_matches_parent(movement: DeliveryMovement, *, parent_state: str = "", parent_city: str = "") -> bool:
    """Restrict neighborhood drill-down to the requested municipality.

    Records from other municipalities are valid operational data; they are not
    "unresolved" for the municipality currently being inspected.
    """
    address = movement.address
    if not address:
        return False
    state = normalize_state(address.state)
    city = normalize_city(address.city)
    if parent_state and state != normalize_state(parent_state):
        return False
    if parent_city and city != normalize_city(parent_city):
        return False
    return True


def _unresolved_reason(movement: DeliveryMovement, level: str) -> str | None:
    address = movement.address
    if not address:
        return "address_missing"
    if not normalize_state(address.state):
        return "state_missing"
    if not normalize_city(address.city):
        return "city_missing"
    if level == "neighborhood" and not normalize_neighborhood(
        address.district, state=address.state, city=address.city
    ):
        return "district_missing"
    return None


def _movement_attempt_facts(movements: list[DeliveryMovement]):
    movement_ids = [m.pk for m in movements]
    facts = defaultdict(lambda: {"delivered": False, "retention": False, "time_window": False, "has_rom": False})
    if not movement_ids:
        return facts

    rows = DeliveryOccurrence.objects.filter(
        movement_id__in=movement_ids,
        source=ROM_SOURCE,
    ).only("movement_id", "code", "description", "occurred_at", "source")
    for occurrence in rows:
        fact = facts[occurrence.movement_id]
        fact["has_rom"] = True
        fact["delivered"] = fact["delivered"] or _is_delivered(occurrence.code, occurrence.description)
        fact["retention"] = fact["retention"] or _is_retention(occurrence.code, occurrence.description)
        fact["time_window"] = fact["time_window"] or _is_time_window(occurrence.code, occurrence.description)

    # Exportações antigas podem não possuir trilha ROM. Nesse caso usamos status
    # do movimento como fallback, mas jamais transformamos CTRC entregue em
    # "entrega daquela tentativa" quando existe uma ocorrência ROM explícita.
    for movement in movements:
        fact = facts[movement.pk]
        if not fact["has_rom"]:
            fact["delivered"] = _is_delivered("", movement.status)
            fact["retention"] = _is_retention("", movement.status)
            fact["time_window"] = _is_time_window("", movement.status)
    return facts


def _cte_total_attempts(cte_ids: set[int]) -> dict[int, int]:
    if not cte_ids:
        return {}
    return dict(
        DeliveryMovement.objects.filter(cte_id__in=cte_ids)
        .values("cte_id")
        .annotate(total=Count("id"))
        .values_list("cte_id", "total")
    )


def _proof_counts_by_region(level: str, *, parent_state: str = "", parent_city: str = "", as_of: date | None = None):
    rows = RetainedProof.objects.exclude(status=RetainedProof.Status.CANCELED).exclude(address=None)
    if as_of is not None:
        rows = rows.filter(retained_at__date__lte=as_of).filter(
            Q(recovered_at__isnull=True) | Q(recovered_at__date__gt=as_of)
        )
    else:
        rows = rows.filter(status__in=OPEN_PROOF_STATUSES)
    rows = rows.select_related("address").only(
        "id", "retained_at", "recovered_at", "address__state", "address__city", "address__district"
    )
    counts = Counter()
    for proof in rows:
        address = proof.address
        state = normalize_state(address.state)
        city = normalize_city(address.city)
        if level == "municipality":
            key = (state, city) if state and city else None
        else:
            if parent_state and state != normalize_state(parent_state):
                continue
            if parent_city and city != normalize_city(parent_city):
                continue
            district = normalize_neighborhood(address.district, state=state, city=city)
            key = (state, city, district) if state and city and district else None
        if key:
            counts[key] += 1
    return counts


def _choose_level(movements: list[DeliveryMovement]) -> tuple[str, str, str]:
    city_counts = Counter()
    display_names: dict[tuple[str, str], tuple[str, str]] = {}
    total = 0
    for movement in movements:
        address = movement.address
        if not address:
            continue
        state = normalize_state(address.state)
        city = normalize_city(address.city)
        if not state or not city:
            continue
        total += 1
        city_counts[(state, city)] += 1
        display_names[(state, city)] = (display_geo(address.state).upper(), display_geo(address.city))
    if not city_counts or not total:
        return "municipality", "", ""
    (state, city), count = city_counts.most_common(1)[0]
    if count / total >= GEO_DOMINANT_CITY_THRESHOLD:
        # O nível bairro não depende mais exclusivamente de uma malha estática
        # pré-cadastrada. Se a operação real possui bairros/regiões nesse
        # município, o resolvedor dinâmico pode tentar carregá-los e o fallback
        # textual continua preservando os dados que não tiverem polígono.
        has_districts = any(
            m.address
            and normalize_state(m.address.state) == state
            and normalize_city(m.address.city) == city
            and bool(normalize_neighborhood(m.address.district, state=state, city=city))
            for m in movements
        )
        if neighborhood_provider(state, city) or has_districts:
            return "neighborhood", state, city
    return "municipality", "", ""


def _metric_value(row: dict, metric: str):
    return row.get(metric, 0)


def _safe_rate(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _serialize_decimal(value: Decimal | int | float) -> float:
    return float(value or 0)


def _display_for_region(key, level, display_names):
    if level == "municipality":
        return display_names.get(key, (key[0], key[1]))[1]
    # Para bairros, o nome CANÔNICO precisa acompanhar a chave normalizada.
    # Usar o texto bruto da última linha fazia TAPANA (ICOARACI) deixar de casar
    # com o polígono TAPANA, embora os dados existissem.
    return key[2].title()


def build_geo_summary(
    start: date,
    end: date,
    *,
    branch: str | None = None,
    metric: str = "delivered",
    level: str = "auto",
    parent_state: str = "",
    parent_city: str = "",
    driver_id: int | None = None,
):
    branch = validate_branch(branch)
    if metric not in METRICS:
        metric = "delivered"

    qs = (
        operational_movements_for_period(start, end)
        .filter(driver__is_test=False)
        .exclude(status__iexact="CANCELADO")
        .exclude(manifest__status__iexact="CANCELADO")
        .select_related("address", "client", "driver", "cte", "manifest")
        .only(
            "id", "cte_id", "manifest_id", "driver_id", "client_id", "address_id",
            "status", "weight_kg", "volumes", "movement_date",
            "address__state", "address__city", "address__district", "address__postal_code",
            "address__street", "address__latitude", "address__longitude",
            "client__name", "driver__name", "manifest__number",
        )
    )
    if driver_id:
        qs = qs.filter(driver_id=driver_id)
    movements = list(qs)

    if level == "auto":
        chosen_level, auto_state, auto_city = _choose_level(movements)
        level = chosen_level
        if chosen_level == "neighborhood":
            parent_state = auto_state
            parent_city = auto_city
    level = level if level in {"municipality", "neighborhood"} else "municipality"

    # In a neighborhood drill-down, data from other municipalities must not be
    # counted as "sem localização suficiente". They remain available at the
    # municipality level and are simply outside the selected parent context.
    if level == "neighborhood" and (parent_state or parent_city):
        movements = [
            movement for movement in movements
            if _movement_matches_parent(movement, parent_state=parent_state, parent_city=parent_city)
        ]

    facts = _movement_attempt_facts(movements)
    cte_attempts = _cte_total_attempts({m.cte_id for m in movements})
    proof_counts = _proof_counts_by_region(level, parent_state=parent_state, parent_city=parent_city, as_of=end)

    quality = Counter()
    for movement in movements:
        address = movement.address
        if not address or not normalize_city(address.city):
            quality["UNRESOLVED"] += 1
            continue
        state_n = normalize_state(address.state)
        city_n = normalize_city(address.city)
        district_raw = normalize_geo(address.district)
        district_norm = normalize_neighborhood(address.district, state=state_n, city=city_n)
        if address.latitude is not None and address.longitude is not None:
            quality["EXACT"] += 1
        elif district_norm and district_norm != district_raw:
            quality["INFERRED"] += 1
        elif district_norm:
            quality["NEIGHBORHOOD"] += 1
        elif normalize_geo(address.postal_code):
            quality["ZIP_CODE"] += 1
        else:
            quality["MUNICIPALITY"] += 1

    rows: dict[tuple, dict] = {}
    unresolved = 0
    unresolved_reasons = Counter()
    unresolved_details = []
    display_names: dict[tuple, tuple] = {}
    for movement in movements:
        key = _region_key(movement, level, parent_state=parent_state, parent_city=parent_city)
        if key is None:
            unresolved += 1
            reason = _unresolved_reason(movement, level) or "region_unresolved"
            unresolved_reasons[reason] += 1
            if len(unresolved_details) < 50:
                address = movement.address
                unresolved_details.append({
                    "movement_id": movement.pk,
                    "cte": getattr(movement.cte, "ctrc", "") or "",
                    "nf": getattr(movement.cte, "invoice_number", "") or "",
                    "manifest": getattr(movement.manifest, "number", "") or "",
                    "client": getattr(movement.client, "name", "") or "",
                    "state": display_geo(address.state) if address else "Não informado",
                    "city": display_geo(address.city) if address else "Não informado",
                    "district": display_geo(address.district) if address else "Não informado",
                    "reason": reason,
                })
            continue
        address = movement.address
        if level == "municipality":
            display_names[key] = (display_geo(address.state).upper(), display_geo(address.city))
        else:
            display_names[key] = (
                display_geo(address.state).upper(),
                display_geo(address.city),
                display_geo(address.district),
            )
        row = rows.setdefault(key, {
            "attempts": 0,
            "delivered": 0,
            "retentions": 0,
            "time_window_failures": 0,
            "active_proofs": 0,
            "clean_deliveries": 0,
            "weight_kg": Decimal("0"),
            "volumes": 0,
            "client_ids": set(),
            "driver_ids": set(),
            "manifest_ids": set(),
            "district_names": set(),
        })
        fact = facts[movement.pk]
        row["attempts"] += 1
        row["delivered"] += 1 if fact["delivered"] else 0
        row["retentions"] += 1 if fact["retention"] else 0
        row["time_window_failures"] += 1 if fact["time_window"] else 0
        # V1: "limpa" = entrega desta tentativa, sem 34/13 e sem outra tentativa
        # conhecida do mesmo CT-e. A classificação completa de outras ocorrências
        # negativas seguirá homologação futura.
        is_clean = (
            fact["delivered"]
            and not fact["retention"]
            and not fact["time_window"]
            and cte_attempts.get(movement.cte_id, 1) == 1
        )
        row["clean_deliveries"] += 1 if is_clean else 0
        row["weight_kg"] += movement.weight_kg or Decimal("0")
        row["volumes"] += int(movement.volumes or 0)
        if movement.client_id:
            row["client_ids"].add(movement.client_id)
        if movement.driver_id:
            row["driver_ids"].add(movement.driver_id)
        if movement.address and movement.address.district:
            district_n = normalize_neighborhood(movement.address.district, state=key[0], city=key[1])
            if district_n:
                row["district_names"].add(district_n)
        row["manifest_ids"].add(movement.manifest_id)

    regions = []
    for key, row in rows.items():
        row["active_proofs"] = int(proof_counts.get(key, 0))
        row["clients"] = len(row.pop("client_ids"))
        row["drivers"] = len(row.pop("driver_ids"))
        row["routes"] = len(row.pop("manifest_ids"))
        district_names = sorted(row.pop("district_names"))
        row["retention_rate"] = _safe_rate(row["retentions"], row["attempts"])
        row["time_window_rate"] = _safe_rate(row["time_window_failures"], row["attempts"])
        row["clean_delivery_rate"] = _safe_rate(row["clean_deliveries"], row["attempts"])
        row["success_rate"] = _safe_rate(row["delivered"], row["attempts"])
        row["weight_kg"] = _serialize_decimal(row["weight_kg"])
        name = _display_for_region(key, level, display_names)
        city_display = display_names.get(key, (key[0], key[1]))[1]
        static_neighborhood_provider = bool(neighborhood_provider(key[0], city_display)) if level == "municipality" else True
        neighborhood_mode = ("static" if static_neighborhood_provider else ("dynamic" if district_names else "none")) if level == "municipality" else "current"
        region = {
            "id": "|".join(key),
            "name": name,
            "state": key[0],
            "city": city_display,
            "has_neighborhood_geometry": (static_neighborhood_provider or bool(district_names)) if level == "municipality" else True,
            "neighborhood_geometry_mode": neighborhood_mode,
            "neighborhood_count": len(district_names) if level == "municipality" else 0,
            **row,
        }
        if level == "neighborhood":
            region["neighborhood"] = name
        region["value"] = _metric_value(region, metric)
        regions.append(region)

    metric_def = METRICS[metric]
    reverse = True  # ranking mostra maiores valores; alertas interpretam sentido abaixo.
    regions.sort(key=lambda r: (r["value"], r["attempts"]), reverse=reverse)

    total_attempts = sum(r["attempts"] for r in regions)
    map_regions = list(regions)
    outliers = []
    # Sem centroids persistidos na V1, usamos um critério conservador de massa
    # operacional: só isolamos cauda minúscula quando existe região claramente
    # dominante. Isso evita que uma única entrega distante destrua o enquadramento.
    if level == "municipality" and total_attempts and regions:
        by_attempts = sorted(regions, key=lambda r: r["attempts"], reverse=True)
        dominance = by_attempts[0]["attempts"] / total_attempts
        if dominance >= GEO_OUTLIER_DOMINANCE_THRESHOLD:
            outliers = [r for r in by_attempts[1:] if (r["attempts"] / total_attempts) < GEO_OUTLIER_MIN_SHARE]
            outlier_ids = {r["id"] for r in outliers}
            map_regions = [r for r in regions if r["id"] not in outlier_ids]

    total_delivered = sum(r["delivered"] for r in regions)
    total_retentions = sum(r["retentions"] for r in regions)
    total_time = sum(r["time_window_failures"] for r in regions)
    total_clean = sum(r["clean_deliveries"] for r in regions)
    total_weight = sum(r["weight_kg"] for r in regions)
    total_clients = len({m.client_id for m in movements if m.client_id})

    alerts = []
    avg_retention_rate = _safe_rate(total_retentions, total_attempts)
    avg_time_rate = _safe_rate(total_time, total_attempts)
    for region in regions:
        if region["attempts"] < GEO_ALERT_MIN_SAMPLE:
            continue
        if region["retention_rate"] > avg_retention_rate and region["retentions"]:
            alerts.append({
                "severity": "high" if region["retention_rate"] >= max(avg_retention_rate * 1.75, 10) else "medium",
                "region": region["name"],
                "type": "retention",
                "message": f"Taxa de retenção {region['retention_rate']:.1f}% acima da média {avg_retention_rate:.1f}%.",
            })
        if region["time_window_rate"] > avg_time_rate and region["time_window_failures"]:
            alerts.append({
                "severity": "medium",
                "region": region["name"],
                "type": "time_window",
                "message": f"Horário em {region['time_window_rate']:.1f}% das tentativas; média {avg_time_rate:.1f}%.",
            })
        if region["active_proofs"] >= 3:
            alerts.append({
                "severity": "medium",
                "region": region["name"],
                "type": "proofs",
                "message": f"{region['active_proofs']} comprovantes atualmente retidos na região.",
            })
    alerts = alerts[:8]

    states = sorted({r["state"] for r in regions if r["state"]})
    geometry = {
        "level": level,
        "urls": [],
        "feature_name_properties": [],
        "feature_code_properties": [],
        "locality_sources": [],
        "provider": "IBGE",
    }
    if level == "neighborhood":
        provider = neighborhood_provider(parent_state, parent_city)
        if provider:
            geometry.update({
                "urls": [provider["url"]],
                "feature_name_properties": provider["feature_name_properties"],
                "provider": provider["source_label"],
            })
        elif regions:
            # Carregador dinâmico: resolve somente os bairros/regiões que realmente
            # aparecem na operação do município e persiste o resultado em cache.
            districts = [r["name"] for r in regions if r.get("attempts")]
            geometry.update({
                "urls": ["/operacao/api/geografia/bairros/?" + urlencode({
                    "state": normalize_state(parent_state),
                    "city": parent_city,
                    "districts": "|".join(districts[:25]),
                })],
                "feature_name_properties": ["name", "canonical_name"],
                "provider": "Resolvedor dinâmico OpenStreetMap/Nominatim + cache local",
            })
    else:
        geometry.update({
            "urls": municipality_geometry_urls(states),
            # A API de Malhas do IBGE normalmente identifica cada feição pelo
            # geocódigo `codarea`, sem anexar o nome do município. O frontend
            # resolve esse código com a API oficial de Localidades por UF.
            "feature_name_properties": ["nome", "nomearea", "NM_MUN", "name"],
            "feature_code_properties": ["codarea", "CD_MUN", "id"],
            "locality_sources": municipality_locality_sources(states),
            "provider": "IBGE API de Malhas v3 + Localidades v1",
        })

    return {
        "branch": branch,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "level": level,
        "parent": {"state": normalize_state(parent_state), "city": normalize_city(parent_city)},
        "metric": {
            "key": metric_def.key,
            "label": metric_def.label,
            "format": metric_def.format,
            "higher_is_better": metric_def.higher_is_better,
            "palette": metric_def.palette,
        },
        "metrics": [m.__dict__ for m in METRICS.values()],
        "regions": regions,
        "map_regions": map_regions,
        "outliers": outliers,
        "outlier_attempts": sum(r["attempts"] for r in outliers),
        "ranking": regions[:5],
        "alerts": alerts,
        "summary": {
            "attempts": total_attempts,
            "delivered": total_delivered,
            "clients": total_clients,
            "weight_kg": round(total_weight, 3),
            "retentions": total_retentions,
            "time_window_failures": total_time,
            "clean_deliveries": total_clean,
            "active_proofs": sum(r["active_proofs"] for r in regions),
            "success_rate": _safe_rate(total_delivered, total_attempts),
            "retention_rate": avg_retention_rate,
            "time_window_rate": avg_time_rate,
            "clean_delivery_rate": _safe_rate(total_clean, total_attempts),
            "regions": len(regions),
            "unresolved": unresolved,
            "unresolved_reasons": dict(unresolved_reasons),
            "geo_quality": dict(quality),
        },
        "unresolved_details": unresolved_details,
        "unresolved_reason_labels": {
            "address_missing": "Endereço não informado",
            "state_missing": "UF não informada",
            "city_missing": "Município não informado",
            "district_missing": "Bairro não informado",
            "region_unresolved": "Região não reconhecida",
            "geometry_unavailable": "Geometria não disponível",
        },
        "geometry": geometry,
        "home_region": {
            "state": normalize_state(getattr(settings, "GEO_HOME_STATE", "")),
            "city": str(getattr(settings, "GEO_HOME_CITY", "") or "").strip(),
        },
        "limitations": {
            "mixed_branch_database": False,
            "neighborhood_geometry_available": bool(geometry["urls"]) if level == "neighborhood" else True,
        },
    }


def cached_geo_summary(*args, **kwargs):
    start = kwargs.get("start") or (args[0] if args else None)
    end = kwargs.get("end") or (args[1] if len(args) > 1 else None)
    branch = kwargs.get("branch") or active_branch()
    metric = kwargs.get("metric", "delivered")
    level = kwargs.get("level", "auto")
    parent_state = kwargs.get("parent_state", "")
    parent_city = kwargs.get("parent_city", "")
    driver_id = kwargs.get("driver_id")
    key = "geo:v2:" + ":".join(map(str, [branch, start, end, metric, level, parent_state, parent_city, driver_id or "all"]))
    cached = cache.get(key)
    if cached is not None:
        return cached
    payload = build_geo_summary(*args, **kwargs)
    cache.set(key, payload, timeout=60)
    return payload
