from __future__ import annotations

"""Escrita JSON resiliente para Windows.

Objetivo: arquivos de observabilidade/controle não podem derrubar o fluxo do robô
por bloqueios transitórios do Windows/antivírus/indexadores.

O módulo é propositalmente stdlib-only para poder ser testado sem Django.
"""

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

SAFE_JSON_BUILD = "0.3.0.6-win-file-lock"
_RECOVERABLE_WINERRORS = {5, 32, 33}  # access denied / sharing / lock violation


def _is_recoverable_file_lock(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    winerror = getattr(exc, "winerror", None)
    if winerror in _RECOVERABLE_WINERRORS:
        return True
    errno = getattr(exc, "errno", None)
    # EACCES / EPERM on non-Windows filesystems are treated equivalently.
    return errno in {1, 13}


def _unique_tmp(path: Path) -> Path:
    token = f"{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}"
    return path.parent / f".{path.name}.{token}.tmp"


def resilient_atomic_json_write(
    path: Path | str,
    payload: dict[str, Any],
    *,
    transform: Callable[[Any], Any] | None = None,
    best_effort: bool = False,
    retries: int = 12,
    base_delay: float = 0.05,
    max_delay: float = 0.50,
    indent: int | None = 2,
) -> bool:
    """Grava JSON usando temporário exclusivo + replace com retry.

    Retorna ``True`` quando o destino foi atualizado.

    Com ``best_effort=True`` uma falha definitiva de escrita não é propagada:
    o arquivo temporário é preservado como ``*.write_failed.*.json`` quando
    possível e a função retorna ``False``. Isso é adequado para ``status.json``
    e outros artefatos de telemetria.

    Com ``best_effort=False`` a última exceção é propagada após os retries.
    Use esse modo quando o artefato for necessário para consistência do fluxo.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = transform(payload) if transform else payload
    encoded = json.dumps(data, ensure_ascii=False, indent=indent)
    tmp = _unique_tmp(target)

    try:
        tmp.write_text(encoded, encoding="utf-8")
    except Exception:
        if best_effort:
            return False
        raise

    attempts = max(1, int(retries))
    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            os.replace(tmp, target)
            return True
        except OSError as exc:
            last_exc = exc
            if not _is_recoverable_file_lock(exc):
                break
            if attempt + 1 >= attempts:
                break
            delay = min(max_delay, base_delay * (2 ** min(attempt, 4)))
            time.sleep(max(0.0, delay))

    if best_effort:
        try:
            fallback = target.parent / (
                f"{target.name}.write_failed.{os.getpid()}."
                f"{threading.get_ident()}.{uuid.uuid4().hex}.json"
            )
            os.replace(tmp, fallback)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        return False

    try:
        tmp.unlink(missing_ok=True)
    except Exception:
        pass
    if last_exc is not None:
        raise last_exc
    raise OSError(f"Não foi possível substituir {target}")
