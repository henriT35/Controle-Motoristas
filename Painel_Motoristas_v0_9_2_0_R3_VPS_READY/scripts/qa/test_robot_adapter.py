"""QA portátil do ROBÔ SSW homologado atual.

O antigo painel_adapter.py deixou de fazer parte da arquitetura no P13. Este
verificador valida o manifesto SHA-256 e executa o contrato mock oficial do
core sem acessar SSW real nem alterar o core homologado.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROBOT = ROOT / "robot_ssw"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    manifest = ROBOT / "HOMOLOGATED_CORE.sha256"
    if not manifest.exists():
        print("ROBOT CORE MANIFEST: FAIL — manifesto ausente")
        return 1
    failures = []
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(None, 1)
        target = ROBOT / rel.strip()
        checked += 1
        if not target.exists() or sha256(target) != expected:
            failures.append(rel.strip())
    if failures:
        print(f"ROBOT CORE MANIFEST: FAIL — {failures}")
        return 1
    print(f"ROBOT CORE MANIFEST: PASS — {checked}/{checked} arquivos")

    contract = ROBOT / "mock_contract_test.py"
    cp = subprocess.run(
        [sys.executable, str(contract)],
        cwd=str(ROBOT),
        text=True,
        capture_output=True,
    )
    print(cp.stdout, end="")
    if cp.returncode != 0:
        print(cp.stderr, end="", file=sys.stderr)
        print("ROBOT MOCK CONTRACT: FAIL")
        return cp.returncode or 1
    print("ROBOT MOCK CONTRACT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
