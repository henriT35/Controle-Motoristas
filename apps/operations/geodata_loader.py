from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from .geo import normalize_geo, normalize_state, normalize_city, normalize_neighborhood

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "PainelMotoristas/0.6 (geodata-cache; operational-dashboard)"


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
            return data
    except Exception:
        pass
    return {"features": {}, "unresolved": {}, "source": "OpenStreetMap/Nominatim"}


def _save_cache(state: str, city: str, data: dict):
    path = _cache_path(state, city)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _search_polygon(state: str, city: str, district: str):
    query = f"{district}, {city}, {state}, Brasil"
    params = urlencode({
        "q": query,
        "format": "geojson",
        "polygon_geojson": 1,
        "addressdetails": 1,
        "limit": 3,
        "countrycodes": "br",
    })
    req = Request(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json, application/json"})
    with urlopen(req, timeout=18) as response:
        payload = json.loads(response.read().decode("utf-8"))
    for feature in payload.get("features", []) if isinstance(payload, dict) else []:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        props = feature.setdefault("properties", {})
        address = props.get("address") or {}
        returned_city = normalize_city(
            address.get("city") or address.get("town") or address.get("municipality") or address.get("county") or ""
        )
        # Se Nominatim informou outra cidade explicitamente, não força associação.
        if returned_city and normalize_city(city) not in returned_city and returned_city not in normalize_city(city):
            continue
        return feature
    return None


def neighborhood_feature_collection(state: str, city: str, districts: list[str], *, allow_network=True) -> tuple[dict, dict]:
    """Resolve somente bairros realmente presentes na operação e persiste cache.

    O primeiro acesso pode consultar Nominatim sequencialmente. Resultados e
    falhas ficam cacheados, evitando downloads repetidos em toda abertura.
    """
    state_n = normalize_state(state)
    city_n = normalize_city(city)
    requested = []
    for value in districts:
        district_n = normalize_neighborhood(value, state=state_n, city=city_n)
        if district_n and district_n not in requested:
            requested.append(district_n)
    requested = requested[:25]
    cache = _load_cache(state_n, city_n)
    features = cache.setdefault("features", {})
    unresolved = cache.setdefault("unresolved", {})
    changed = False

    for district in requested:
        if district in features or district in unresolved:
            continue
        if not allow_network:
            unresolved[district] = "not_cached"
            changed = True
            continue
        try:
            feature = _search_polygon(state_n, city_n, district)
            if feature:
                feature.setdefault("properties", {})["name"] = district.title()
                feature["properties"]["canonical_name"] = district
                feature["properties"]["source"] = "OpenStreetMap/Nominatim"
                features[district] = feature
            else:
                unresolved[district] = "polygon_not_found"
            changed = True
        except Exception as exc:
            unresolved[district] = f"fetch_error:{type(exc).__name__}"
            changed = True
        # Política conservadora para serviço público; só ocorre em cache miss.
        time.sleep(1.05)

    if changed:
        _save_cache(state_n, city_n, cache)

    selected = [features[d] for d in requested if d in features]
    meta = {
        "state": state_n,
        "city": city_n,
        "requested": requested,
        "resolved": [d for d in requested if d in features],
        "unresolved": {d: unresolved.get(d) for d in requested if d not in features},
        "cache_file": str(_cache_path(state_n, city_n)),
    }
    return {"type": "FeatureCollection", "features": selected}, meta
