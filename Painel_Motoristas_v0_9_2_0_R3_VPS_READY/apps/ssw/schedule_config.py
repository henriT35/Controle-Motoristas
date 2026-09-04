from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

CONFIG_FILE = Path(settings.BASE_DIR) / "local_data" / "ssw_schedule.json"
SCHEDULER_STATE_FILE = Path(settings.BASE_DIR) / "local_data" / "ssw_scheduler_state.json"
MIN_INTERVAL_MINUTES = 15
MAX_INTERVAL_MINUTES = 24 * 60

DEFAULTS = {
    "enabled": True,
    # Mantido por compatibilidade com telas/configs antigas. A fonte real da
    # cadência na v0.8.2.0 passa a ser routines[].interval_minutes.
    "interval_minutes": 120,
    "routines": [
        {
            "id": "rotas-do-dia",
            "name": "Rotas do dia",
            "enabled": True,
            "range_mode": "RECENT",
            "recent_days": 2,
            "start_date": "",
            "end_date": "",
            "interval_minutes": 120,
            "active_from": "05:00",
            "active_until": "23:30",
            "last_triggered_at": None,
            "last_run_ids": [],
        }
    ],
}


def _coerce_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _coerce_interval(value, default=120):
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = default
    return max(MIN_INTERVAL_MINUTES, min(interval, MAX_INTERVAL_MINUTES))


def _coerce_recent_days(value, default=2):
    try:
        days = int(value)
    except (TypeError, ValueError):
        days = default
    return max(1, min(days, 31))


def _clean_clock(value, default):
    parsed = parse_time(str(value or "").strip())
    return parsed.strftime("%H:%M") if parsed else default


def _clean_date(value):
    parsed = parse_date(str(value or "").strip())
    return parsed.isoformat() if parsed else ""


def _routine_id(value=None):
    raw = str(value or "").strip()
    if raw:
        return raw[:80]
    return uuid.uuid4().hex[:12]


def _normalise_routine(raw: dict | None, *, default_interval=120) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    mode = str(raw.get("range_mode") or "RECENT").upper().strip()
    if mode not in {"RECENT", "FIXED"}:
        mode = "RECENT"
    name = str(raw.get("name") or ("Rotas do dia" if mode == "RECENT" else "Período fixo")).strip()[:80]
    return {
        "id": _routine_id(raw.get("id")),
        "name": name or "Rotina SSW",
        "enabled": _coerce_bool(raw.get("enabled"), True),
        "range_mode": mode,
        "recent_days": _coerce_recent_days(raw.get("recent_days"), 2),
        "start_date": _clean_date(raw.get("start_date")),
        "end_date": _clean_date(raw.get("end_date")),
        "interval_minutes": _coerce_interval(raw.get("interval_minutes"), default_interval),
        "active_from": _clean_clock(raw.get("active_from"), "00:00"),
        "active_until": _clean_clock(raw.get("active_until"), "23:59"),
        "last_triggered_at": raw.get("last_triggered_at") or None,
        "last_run_ids": [int(x) for x in (raw.get("last_run_ids") or []) if str(x).isdigit()][:64],
    }


def _atomic_write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_schedule_config() -> dict:
    """Carrega a agenda SSW compartilhada por web, scheduler local e Celery Beat.

    Compatibilidade: arquivos antigos tinham apenas enabled + interval_minutes.
    Na primeira leitura eles viram uma rotina RECENT equivalente, sem migration.
    """
    data = deepcopy(DEFAULTS)
    raw = None
    try:
        parsed = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            raw = parsed
    except Exception:
        raw = None

    if raw:
        data["enabled"] = _coerce_bool(raw.get("enabled"), True)
        legacy_interval = _coerce_interval(raw.get("interval_minutes"), 120)
        routines = raw.get("routines")
        if isinstance(routines, list) and routines:
            data["routines"] = [_normalise_routine(item, default_interval=legacy_interval) for item in routines]
        else:
            # Upgrade transparente da v0.8.1.0: preserva o intervalo que o
            # usuário já havia configurado no painel.
            upgraded = deepcopy(DEFAULTS["routines"][0])
            upgraded["interval_minutes"] = legacy_interval
            data["routines"] = [_normalise_routine(upgraded, default_interval=legacy_interval)]
        data["interval_minutes"] = legacy_interval
    elif not CONFIG_FILE.exists():
        # Bootstrap por ambiente continua útil na VPS antes da primeira edição.
        data["enabled"] = _coerce_bool(os.getenv("SSW_AUTO_SYNC_ENABLED"), True)
        if os.getenv("SSW_AUTO_SYNC_INTERVAL_MINUTES"):
            interval = _coerce_interval(os.getenv("SSW_AUTO_SYNC_INTERVAL_MINUTES"), 120)
            data["interval_minutes"] = interval
            data["routines"][0]["interval_minutes"] = interval

    data["enabled"] = _coerce_bool(data.get("enabled"), True)
    data["routines"] = [_normalise_routine(item, default_interval=data.get("interval_minutes", 120)) for item in data.get("routines", [])]
    if not data["routines"]:
        data["routines"] = [_normalise_routine(DEFAULTS["routines"][0])]
    enabled_routines = [r for r in data["routines"] if r["enabled"]]
    data["interval_minutes"] = (enabled_routines[0] if enabled_routines else data["routines"][0])["interval_minutes"]
    return data


def save_schedule_config(*, enabled: bool, interval_minutes: int | None = None) -> dict:
    """Compatibilidade com o formulário antigo: altera o mestre da agenda.

    Se interval_minutes vier preenchido, também atualiza a primeira rotina.
    """
    data = load_schedule_config()
    data["enabled"] = bool(enabled)
    if interval_minutes is not None and data["routines"]:
        data["routines"][0]["interval_minutes"] = _coerce_interval(interval_minutes, data["routines"][0]["interval_minutes"])
    data["interval_minutes"] = data["routines"][0]["interval_minutes"]
    _atomic_write(CONFIG_FILE, data)
    return data


def save_routine(payload: dict) -> tuple[dict, dict]:
    data = load_schedule_config()
    incoming = _normalise_routine(payload)
    existing = next((r for r in data["routines"] if r["id"] == incoming["id"]), None)
    if existing:
        # Estado de execução pertence ao scheduler, não ao formulário.
        incoming["last_triggered_at"] = existing.get("last_triggered_at")
        incoming["last_run_ids"] = list(existing.get("last_run_ids") or [])
        idx = data["routines"].index(existing)
        data["routines"][idx] = incoming
    else:
        data["routines"].append(incoming)
    data["interval_minutes"] = incoming["interval_minutes"]
    _atomic_write(CONFIG_FILE, data)
    return data, incoming


def delete_routine(routine_id: str) -> dict:
    data = load_schedule_config()
    data["routines"] = [r for r in data["routines"] if r["id"] != routine_id]
    if not data["routines"]:
        data["routines"] = [_normalise_routine(DEFAULTS["routines"][0])]
    data["interval_minutes"] = data["routines"][0]["interval_minutes"]
    _atomic_write(CONFIG_FILE, data)
    return data


def get_routine(routine_id: str) -> dict | None:
    return next((r for r in load_schedule_config()["routines"] if r["id"] == routine_id), None)


def mark_routine_triggered(routine_id: str, run_ids: list[int], triggered_at=None) -> dict:
    data = load_schedule_config()
    stamp = (triggered_at or timezone.now()).isoformat()
    for routine in data["routines"]:
        if routine["id"] == routine_id:
            routine["last_triggered_at"] = stamp
            routine["last_run_ids"] = [int(x) for x in run_ids][:64]
            break
    _atomic_write(CONFIG_FILE, data)
    return data


def interval_label(minutes: int) -> str:
    minutes = _coerce_interval(minutes)
    if minutes < 60:
        return f"A cada {minutes} minutos"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"A cada {hours} hora" if hours == 1 else f"A cada {hours} horas"
    return f"A cada {minutes} minutos"


def routine_period(routine: dict, today: date | None = None) -> tuple[date, date] | None:
    today = today or timezone.localdate()
    if routine.get("range_mode") == "FIXED":
        start = parse_date(routine.get("start_date") or "")
        end = parse_date(routine.get("end_date") or "")
        if not start or not end:
            return None
        if start > end:
            start, end = end, start
        if start > today:
            return None
        return start, min(end, today)
    days = _coerce_recent_days(routine.get("recent_days"), 2)
    return today - timedelta(days=days - 1), today


def routine_period_label(routine: dict) -> str:
    if routine.get("range_mode") == "FIXED":
        start = parse_date(routine.get("start_date") or "")
        end = parse_date(routine.get("end_date") or "")
        if start and end:
            return f"{start.strftime('%d/%m/%Y')} até {end.strftime('%d/%m/%Y')}"
        return "Período fixo incompleto"
    days = _coerce_recent_days(routine.get("recent_days"), 2)
    return "Somente hoje" if days == 1 else f"Últimos {days} dias"


def _parse_iso(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except Exception:
        return None


def routine_is_in_active_window(routine: dict, now=None) -> bool:
    now = timezone.localtime(now or timezone.now())
    start = parse_time(routine.get("active_from") or "00:00") or time.min
    end = parse_time(routine.get("active_until") or "23:59") or time.max
    current = now.time().replace(tzinfo=None)
    if start <= end:
        return start <= current <= end
    # Janela atravessando meia-noite, ex.: 22:00 → 05:00.
    return current >= start or current <= end


def routine_last_anchor(routine: dict):
    return _parse_iso(routine.get("last_triggered_at"))


def routine_next_due_at(routine: dict, now=None):
    """Próxima referência visual respeitando também a janela diária.

    A decisão real de disparo continua em scheduler_service.routine_due(), que
    também considera jobs ainda ativos. Aqui evitamos mostrar no Painel uma
    "próxima execução" já vencida ou fora do horário configurado.
    """
    now = timezone.localtime(now or timezone.now())
    if not routine.get("enabled") or routine_period(routine, now.date()) is None:
        return None

    anchor = routine_last_anchor(routine)
    candidate = now if not anchor else timezone.localtime(anchor) + timedelta(
        minutes=_coerce_interval(routine.get("interval_minutes"), 120)
    )
    if candidate < now:
        candidate = now

    if routine_is_in_active_window(routine, candidate):
        return candidate

    start = parse_time(routine.get("active_from") or "00:00") or time.min
    end = parse_time(routine.get("active_until") or "23:59") or time.max
    local_candidate = timezone.localtime(candidate)
    current = local_candidate.time().replace(tzinfo=None)

    # Janela normal, ex.: 05:00 -> 23:30.
    if start <= end:
        day = local_candidate.date() if current < start else local_candidate.date() + timedelta(days=1)
    else:
        # Janela atravessa meia-noite. O único intervalo fechado é end -> start.
        day = local_candidate.date()

    next_dt = datetime.combine(day, start)
    if timezone.is_naive(next_dt):
        next_dt = timezone.make_aware(next_dt, timezone.get_current_timezone())
    return timezone.localtime(next_dt)


def load_scheduler_state() -> dict:
    data = {"running": False, "heartbeat": None, "last_cycle": None, "message": "Scheduler ainda não iniciou."}
    try:
        raw = json.loads(SCHEDULER_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update(raw)
    except Exception:
        pass
    heartbeat = _parse_iso(data.get("heartbeat"))
    age = None
    if heartbeat:
        age = max(0, (timezone.now() - heartbeat).total_seconds())
    data["heartbeat_age"] = age
    data["running"] = bool(heartbeat and age is not None and age <= 150)
    return data


def write_scheduler_state(**updates) -> dict:
    data = load_scheduler_state()
    data.update(updates)
    data["heartbeat"] = timezone.now().isoformat()
    _atomic_write(SCHEDULER_STATE_FILE, data)
    return data
