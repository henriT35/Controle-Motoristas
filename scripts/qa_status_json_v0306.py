from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.ssw.safe_json import resilient_atomic_json_write


class WinAccessDenied(PermissionError):
    def __init__(self, message: str = "Acesso negado"):
        super().__init__(13, message)
        self.winerror = 5


def main() -> int:
    real_replace = os.replace
    with tempfile.TemporaryDirectory(prefix="painel-v0306-") as raw:
        root = Path(raw)

        # 1) Bloqueio transitório: deve repetir e concluir sem exceção.
        target = root / "status.json"
        target.write_text('{"state":"OLD"}', encoding="utf-8")
        calls = {"n": 0}

        def flaky_replace(src, dst):
            calls["n"] += 1
            if calls["n"] <= 3:
                raise WinAccessDenied()
            return real_replace(src, dst)

        with patch("apps.ssw.safe_json.os.replace", side_effect=flaky_replace):
            ok = resilient_atomic_json_write(
                target,
                {"state": "DOWNLOADED"},
                best_effort=True,
                retries=6,
                base_delay=0.001,
                max_delay=0.002,
            )
        assert ok is True
        assert json.loads(target.read_text(encoding="utf-8"))["state"] == "DOWNLOADED"
        assert calls["n"] == 4

        # 2) Bloqueio permanente em status.json: não pode derrubar execução.
        status2 = root / "status2.json"
        with patch("apps.ssw.safe_json.os.replace", side_effect=WinAccessDenied()):
            ok = resilient_atomic_json_write(
                status2,
                {"state": "WAITING_DOWNLOAD"},
                best_effort=True,
                retries=3,
                base_delay=0.001,
                max_delay=0.002,
            )
        assert ok is False

        # 3) Artefato obrigatório: após retries, a exceção continua visível.
        result = root / "result.json"
        raised = False
        with patch("apps.ssw.safe_json.os.replace", side_effect=WinAccessDenied()):
            try:
                resilient_atomic_json_write(
                    result,
                    {"robot_status": "DOWNLOADED"},
                    best_effort=False,
                    retries=2,
                    base_delay=0.001,
                    max_delay=0.002,
                )
            except PermissionError:
                raised = True
        assert raised is True

    print("QA v0.3.0.6 PASS: retry transitório + status best-effort + result obrigatório")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
