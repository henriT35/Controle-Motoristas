from __future__ import annotations

"""Progresso de importação fora do banco.

O processamento SSW usa transaction.atomic() para manter o lote consistente. Em
SQLite, gravar o progresso no mesmo banco durante essa transação pode ficar
invisível para a interface até o commit e passa a impressão de que a leitura
travou. Este módulo publica apenas metadados técnicos em um JSON atômico por
ImportRun, permitindo feedback ao vivo sem abrir mão da transação do lote.
"""

import json
from pathlib import Path
from time import time
from typing import Any

from django.conf import settings

from .safe_json import resilient_atomic_json_write


PROGRESS_BUILD = "0.3.0.9-watchdog-import-progress"


def _dir() -> Path:
    target = Path(settings.BASE_DIR) / "local_data" / "import_progress"
    target.mkdir(parents=True, exist_ok=True)
    return target


def progress_path(run_id: int) -> Path:
    return _dir() / f"run_{int(run_id)}.json"


def publish_import_progress(
    run_id: int,
    *,
    phase: str,
    message: str,
    percent: float | int | None = None,
    current: int | None = None,
    total: int | None = None,
    metrics: dict[str, Any] | None = None,
    status: str = "RUNNING",
) -> None:
    """Escreve um snapshot pequeno usando replace atômico.

    Não contém credenciais nem conteúdo de linhas do SSW. Falha de telemetria
    nunca deve derrubar uma importação funcional.
    """
    try:
        payload = {
            "run_id": int(run_id),
            "phase": str(phase),
            "message": str(message)[:1000],
            "percent": None if percent is None else max(0.0, min(100.0, float(percent))),
            "current": current,
            "total": total,
            "metrics": metrics or {},
            "status": str(status),
            "updated_at_epoch": time(),
            "build": PROGRESS_BUILD,
        }
        resilient_atomic_json_write(
            progress_path(run_id),
            payload,
            best_effort=True,
            indent=None,
        )
    except Exception:
        # Progresso é observabilidade; nunca pode comprometer o lote.
        return


def read_import_progress(run_id: int) -> dict[str, Any] | None:
    try:
        path = progress_path(run_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if int(payload.get("run_id", -1)) != int(run_id):
            return None
        return payload
    except Exception:
        return None


def clear_import_progress(run_id: int) -> None:
    """Remove snapshot antigo antes de uma nova tentativa do mesmo ImportRun.

    O watchdog só deve observar progresso gerado pela execução atual. A remoção é
    best-effort porque telemetria nunca pode impedir o fluxo principal.
    """
    try:
        progress_path(run_id).unlink(missing_ok=True)
    except Exception:
        return
