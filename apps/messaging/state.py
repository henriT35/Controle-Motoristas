from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.conf import settings

RUNTIME_DIR = Path(settings.BASE_DIR) / "local_data" / "whatsapp"
STATE_FILE = RUNTIME_DIR / "state.json"
STOP_FILE = RUNTIME_DIR / "stop.request"
RESET_FILE = RUNTIME_DIR / "reset.request"
QR_FILE = RUNTIME_DIR / "qr.png"
SESSION_DIR = RUNTIME_DIR / "baileys_auth"
BRIDGE_TOKEN_FILE = RUNTIME_DIR / "bridge_token.txt"
LOG_FILE = Path(settings.BASE_DIR) / "logs" / "whatsapp_baileys.log"
BRIDGE_DIR = Path(settings.BASE_DIR) / "whatsapp_bridge"


def _now_iso():
    return datetime.now(dt_timezone.utc).isoformat()


def _pid_alive(pid) -> bool:
    try:
        pid = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=flags,
            )
            output = (result.stdout or "").strip()
            return bool(output and not output.upper().startswith("INFO:") and f'"{pid}"' in output)
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def process_alive(pid) -> bool:
    return _pid_alive(pid)


def write_state(**values):
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    try:
        current = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        current = {}
    current.update(values)
    current["heartbeat"] = _now_iso()
    current.setdefault("pid", os.getpid())
    current.setdefault("started_at", _now_iso())
    current.setdefault("backend", "Baileys / Node.js")
    current["qr_available"] = QR_FILE.exists()
    tmp = STATE_FILE.with_name(f"state.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)
    return current


def read_state(raw=False):
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {
            "status": "OFFLINE",
            "connected": False,
            "online": False,
            "pid": None,
            "backend": "Baileys / Node.js",
        }
    if raw:
        return data

    heartbeat_age = None
    heartbeat = data.get("heartbeat")
    if heartbeat:
        try:
            ts = datetime.fromisoformat(str(heartbeat).replace("Z", "+00:00"))
            heartbeat_age = max(0.0, (datetime.now(dt_timezone.utc) - ts).total_seconds())
        except Exception:
            heartbeat_age = None

    external = bool(getattr(settings, "WHATSAPP_BRIDGE_EXTERNAL_SERVICE", False))
    pid_alive = _pid_alive(data.get("pid")) if not external else bool(
        heartbeat_age is not None and heartbeat_age <= 35 and data.get("online", True)
    )
    responsive = bool(pid_alive and heartbeat_age is not None and heartbeat_age <= 35)
    data["process_alive"] = pid_alive
    data["responsive"] = responsive
    data["online"] = pid_alive
    data["managed_externally"] = external
    data["heartbeat_age"] = heartbeat_age
    data["qr_available"] = QR_FILE.exists()
    data.setdefault("backend", "Baileys / Node.js")

    if not pid_alive:
        data["connected"] = False
        if data.get("status") not in {"ERROR", "LOGGED_OUT"}:
            data["status"] = "OFFLINE"
    elif not responsive and data.get("status") not in {"STOPPING"}:
        data["status"] = "UNRESPONSIVE"
        data["connected"] = False
        data["message"] = "O serviço Baileys está aberto, mas parou de atualizar o estado. Você pode encerrá-lo com segurança."
    return data


def request_stop():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text(_now_iso(), encoding="utf-8")


def clear_stop_request():
    try:
        STOP_FILE.unlink()
    except FileNotFoundError:
        pass


def request_reset():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    RESET_FILE.write_text(_now_iso(), encoding="utf-8")


def clear_reset_request():
    try:
        RESET_FILE.unlink()
    except FileNotFoundError:
        pass


def clear_qr_artifacts():
    try:
        QR_FILE.unlink()
    except FileNotFoundError:
        pass


def ensure_bridge_token() -> str:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    try:
        token = BRIDGE_TOKEN_FILE.read_text(encoding="utf-8").strip()
        if len(token) >= 32:
            return token
    except Exception:
        pass
    token = secrets.token_urlsafe(48)
    BRIDGE_TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


def read_bridge_token() -> str:
    try:
        return BRIDGE_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def reset_baileys_session():
    """Apaga somente as credenciais de dispositivo mantidas pelo Baileys.

    A implementação anterior usava profiles Chrome/Edge, IndexedDB e CDP. Esses
    artefatos deixaram de fazer parte do fluxo oficial a partir da v0.7.1.0.
    """
    clear_stop_request()
    clear_reset_request()
    clear_qr_artifacts()
    if SESSION_DIR.exists():
        shutil.rmtree(SESSION_DIR)
    # Mantém o token local do bridge: ele não é credencial do WhatsApp e evita
    # quebrar uma inicialização concorrente do servidor Django.
    return {"session_removed": True}


def reset_state(message="Serviço WhatsApp desligado"):
    clear_stop_request()
    clear_qr_artifacts()
    return write_state(
        status="OFFLINE",
        connected=False,
        online=False,
        pid=None,
        message=message,
        qr_available=False,
        backend="Baileys / Node.js",
        account_jid="",
        account_name="",
        error_code="",
    )


def _node_20_or_newer(candidate: str | Path) -> bool:
    try:
        result = subprocess.run(
            [str(candidate), "-p", "process.versions.node"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        major = int((result.stdout or "0").strip().split(".", 1)[0])
        return major >= 20
    except Exception:
        return False


def find_node_binary() -> str:
    """Retorna Node 20+ do pacote ou do PATH."""
    candidates: list[str | Path] = []
    if os.name == "nt":
        candidates.extend([
            Path(settings.BASE_DIR) / "tools" / "node" / "node.exe",
            Path(settings.BASE_DIR) / "tools" / "node" / "node-v24.20.0-win-x64" / "node.exe",
        ])
    system_node = shutil.which("node")
    if system_node:
        candidates.append(system_node)
    for candidate in candidates:
        if Path(candidate).exists() and _node_20_or_newer(candidate):
            return str(candidate)
    return ""


def bridge_dependencies_ready() -> bool:
    return (BRIDGE_DIR / "node_modules" / "@whiskeysockets" / "baileys" / "package.json").exists()
