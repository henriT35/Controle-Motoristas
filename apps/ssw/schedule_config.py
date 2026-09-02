from __future__ import annotations

import json
import os
from pathlib import Path

from django.conf import settings

CONFIG_FILE = Path(settings.BASE_DIR) / "local_data" / "ssw_schedule.json"
DEFAULTS = {
    "enabled": True,
    "interval_minutes": 60,
}
MIN_INTERVAL_MINUTES = 15
MAX_INTERVAL_MINUTES = 24 * 60


def _coerce_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _coerce_interval(value, default=60):
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = default
    return max(MIN_INTERVAL_MINUTES, min(interval, MAX_INTERVAL_MINUTES))


def load_schedule_config() -> dict:
    """Configuração operacional persistente sem exigir migration.

    O arquivo fica em local_data, que no deploy Docker é um volume persistente
    compartilhado pelo web/worker/beat. Assim a frequência pode ser alterada no
    Painel e lida pelo scheduler em todos os processos.
    """
    data = dict(DEFAULTS)
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update(raw)
    except Exception:
        pass

    # Variáveis de ambiente funcionam como bootstrap inicial. Depois que o
    # arquivo existe, a configuração salva pelo Painel prevalece.
    if not CONFIG_FILE.exists():
        if os.getenv("SSW_AUTO_SYNC_ENABLED") is not None:
            data["enabled"] = _coerce_bool(os.getenv("SSW_AUTO_SYNC_ENABLED"), True)
        if os.getenv("SSW_AUTO_SYNC_INTERVAL_MINUTES"):
            data["interval_minutes"] = _coerce_interval(os.getenv("SSW_AUTO_SYNC_INTERVAL_MINUTES"), 60)

    data["enabled"] = _coerce_bool(data.get("enabled"), True)
    data["interval_minutes"] = _coerce_interval(data.get("interval_minutes"), 60)
    return data


def save_schedule_config(*, enabled: bool, interval_minutes: int) -> dict:
    data = {
        "enabled": bool(enabled),
        "interval_minutes": _coerce_interval(interval_minutes),
    }
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_name(f"{CONFIG_FILE.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)
    return data


def interval_label(minutes: int) -> str:
    minutes = _coerce_interval(minutes)
    if minutes < 60:
        return f"A cada {minutes} minutos"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"A cada {hours} hora" if hours == 1 else f"A cada {hours} horas"
    return f"A cada {minutes} minutos"
