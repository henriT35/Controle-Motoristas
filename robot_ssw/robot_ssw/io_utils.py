from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def sanitize(text: object, secrets: Iterable[str] = ()) -> str:
    value = str(text)
    for secret in secrets:
        if secret:
            value = value.replace(secret, "***")
    return re.sub(
        r"(?i)\b(password|senha|token|cookie|authorization)\b\s*[:=]\s*\S+",
        r"\1=***",
        value,
    )

def atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
