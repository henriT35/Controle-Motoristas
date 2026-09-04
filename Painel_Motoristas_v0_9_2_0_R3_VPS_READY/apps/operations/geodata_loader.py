from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from .geo import normalize_geo, normalize_state, normalize_city, normalize_neighborhood

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PainelMotoristas/0.9.1 (geodata-cache; operational-dashboard)"
RETRY_FETCH_ERROR = timedelta(hours=1)
RETRY_NOT_FOUND = timedelta(days=7)
DISTRICT_ADDRESS_KEYS = ("neighbourhood", "suburb", "quarter", "city_district", "borough")
REJECT_TYPES = {"city", "town", "municipality", "administrative", "county", "state"}


def _cache_path(state: str, city: str) -> Path:
    state_n = normalize_state(state) or "XX"
    city_n = normalize_city(city) or "SEM_CIDADE"
    root = Path(settings.BASE_DIR) / "local_data" / "geodata" / "neighborhoods" / state_n
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{city_n.replace(' ', '_')}.json"


def _load_cache(state: str, city: str) -> dict:
    path = _cache_path(state, city)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("features", {})
            data.setdefault("unresolved", {})
            return data
    except Exception:
        pass
    return {"features": {}, "unresolved": {}, "source": "OpenStreetMap/Nominatim"}


def _save_cache(state: str, city: str, data: dict):
    path = _cache_path(state, city)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _is_valid_district_value(district: str, city: str) -> bool:
    district_n = normalize_geo(district)
    city_n = normalize_city(city)
    if not district_n or district_n == city_n:
        return False
    if district_n in {"ZONA RURAL", "AREA RURAL", "RURAL", "CENTRO DO MUNICIPIO", "SEM BAIRRO", "NAO INFORMADO"}:
        return False
    # Valores muito parecidos com estabelecimentos/logradouro não devem virar polígono.
    bad_tokens = ("RODOVIA ", "BR ", "KM ", "FAZENDA ", "EMPRESA ", "LOJA ", "FILIAL ", "CD ", "GALPAO ")
    return not district_n.startswith(bad_tokens)


def _feature_matches_district(feature: dict, state: str, city: str, district: str) -> bool:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        return False
    props = feature.get("properties") or {}
    address = props.get("address") or {}
    returned_type = normalize_geo(props.get("type") or props.get("addresstype") or "").lower()
    if returned_type in REJECT_TYPES:
        return False
    returned_city = normalize_city(
        address.get("city") or address.get("town") or address.get("municipality") or address.get("county") or ""
    )
    city_n = normalize_city(city)
    if returned_city and returned_city != city_n:
        return False
    district_n = normalize_neighborhood(district, state=state, city=city)
    returned_districts = {
        normalize_neighborhood(address.get(key), state=state, city=city)
        for key in DISTRICT_ADDRESS_KEYS if address.get(key)
    }
    name = normalize_neighborhood(props.get("name") or props.get("display_name", "").split(",", 1)[0], state=state, city=city)
    if name:
        returned_districts.add(name)
    returned_districts.discard("")
    # Regra absoluta: município não pode satisfazer bairro.
    if city_n in returned_districts:
        returned_districts.discard(city_n)
    return district_n in returned_districts


def _search_polygon(state: str, city: str, district: str):
    query = f"{district}, {city}, {state}, Brasil"
    params = urlencode({
        "q": query, "format": "geojson", "polygon_geojson": 1,
        "addressdetails": 1, "limit": 6, "countrycodes": "br",
    })
    req = Request(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json, application/json"})
    with urlopen(req, timeout=18) as response:
        payload = json.loads(response.read().decode("utf-8"))
    for feature in payload.get("features", []) if isinstance(payload, dict) else []:
        if _feature_matches_district(feature, state, city, district):
            return feature
    return None


def _parse_checked_at(item) -> datetime | None:
    if not isinstance(item, dict):
        return None
    raw = item.get("checked_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _retry_due(item) -> bool:
    if not isinstance(item, dict):
        # Cache antigo string: deixa reprocessar na v0.9.1 para corrigir falso negativo eterno.
        return True
    checked = _parse_checked_at(item)
    if not checked:
        return True
    reason = str(item.get("reason") or "")
    ttl = RETRY_FETCH_ERROR if reason.startswith("fetch_error") else RETRY_NOT_FOUND
    return datetime.now(dt_timezone.utc) - checked >= ttl


def neighborhood_feature_collection(state: str, city: str, districts: list[str], *, allow_network=True, force_retry=False) -> tuple[dict, dict]:
    """Resolve bairros sem confundir município e bairro e sem cachear erro eternamente."""
    state_n = normalize_state(state)
    city_n = normalize_city(city)
    requested = []
    rejected = {}
    for value in districts:
        district_n = normalize_neighborhood(value, state=state_n, city=city_n)
        if not _is_valid_district_value(district_n, city_n):
            if district_n:
                rejected[district_n] = {"reason": "invalid_neighborhood_value"}
            continue
        if district_n not in requested:
            requested.append(district_n)
    cache = _load_cache(state_n, city_n)
    features = cache.setdefault("features", {})
    unresolved = cache.setdefault("unresolved", {})
    changed = False

    for district in requested:
        if district in features:
            continue
        previous = unresolved.get(district)
        if previous and not force_retry and not _retry_due(previous):
            continue
        if not allow_network:
            if district not in unresolved:
                unresolved[district] = {"reason": "not_cached", "checked_at": datetime.now(dt_timezone.utc).isoformat()}
                changed = True
            continue
        try:
            feature = _search_polygon(state_n, city_n, district)
            if feature:
                props = feature.setdefault("properties", {})
                props["name"] = district.title()
                props["canonical_name"] = district
                props["source"] = "OpenStreetMap/Nominatim"
                props["validated_as"] = "neighborhood"
                features[district] = feature
                unresolved.pop(district, None)
            else:
                unresolved[district] = {"reason": "polygon_not_found", "checked_at": datetime.now(dt_timezone.utc).isoformat()}
            changed = True
        except Exception as exc:
            unresolved[district] = {"reason": f"fetch_error:{type(exc).__name__}", "checked_at": datetime.now(dt_timezone.utc).isoformat()}
            changed = True
        time.sleep(1.05)

    if changed:
        _save_cache(state_n, city_n, cache)

    selected = [features[d] for d in requested if d in features]
    unresolved_selected = {d: unresolved.get(d) for d in requested if d not in features}
    unresolved_selected.update(rejected)
    meta = {
        "state": state_n, "city": city_n, "requested": requested,
        "resolved": [d for d in requested if d in features],
        "unresolved": unresolved_selected,
        "cache_file": str(_cache_path(state_n, city_n)),
        "rule": "MUNICIPIO != BAIRRO",
    }
    return {"type": "FeatureCollection", "features": selected}, meta
