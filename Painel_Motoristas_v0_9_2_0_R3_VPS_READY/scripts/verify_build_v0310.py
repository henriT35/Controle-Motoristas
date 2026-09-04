from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def ok(label: str, condition: bool, detail: str = "") -> None:
    status = "OK" if condition else "FALHA"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")
    if not condition:
        FAILURES.append(label)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
ok("Versão do pacote", version == "0.3.0.10", version)

engine = (ROOT / "apps/ssw/import_engine_v2.py").read_text(encoding="utf-8")
ok(
    "Correção UNIQUE de clientes",
    "Client.objects.get_or_create(" in engine and "cnpj=candidate.cnpj" in engine and "name=candidate.name" in engine,
)
ok(
    "Sem bulk_create cego de Client",
    re.search(r"Client\.objects\.bulk_create\s*\(", engine) is None,
)

watchdog = (ROOT / "apps/ssw/management/commands/run_ssw_robot_guarded.py").read_text(encoding="utf-8")
ok("Timeout do robô = 900s", 'SSW_ROBOT_TIMEOUT_SECONDS' in watchdog and '900' in watchdog)
ok("Timeout do importador = 3600s", 'SSW_IMPORT_TIMEOUT_SECONDS' in watchdog and '3600' in watchdog)
ok("Erro IMPORT_HARD_TIMEOUT presente", "IMPORT_HARD_TIMEOUT" in watchdog)
ok("Watchdog lê progresso do importador", "read_import_progress" in watchdog)

dispatch = (ROOT / "apps/ssw/dispatch.py").read_text(encoding="utf-8")
ok("Retry priority preservado", "def dispatch_robot_run(run_id" in dispatch and "priority" in dispatch)

parser = (ROOT / "apps/ssw/parsers.py").read_text(encoding="utf-8")
ok("Parser SSW presente", "COD OCORR CTRC" in parser and "COD OCORR ROM" in parser)

manifest = ROOT / "robot_ssw/HOMOLOGATED_CORE.sha256"
all_hashes_ok = True
hash_details: list[str] = []
for raw in manifest.read_text(encoding="utf-8").splitlines():
    raw = raw.strip()
    if not raw:
        continue
    expected, rel = raw.split(maxsplit=1)
    target = ROOT / "robot_ssw" / rel
    if not target.exists():
        all_hashes_ok = False
        hash_details.append(f"ausente:{rel}")
        continue
    got = sha256(target)
    if got.lower() != expected.lower():
        all_hashes_ok = False
        hash_details.append(f"hash:{rel}")
ok("Core homologado robot_ssw", all_hashes_ok, ", ".join(hash_details) if hash_details else "SHA-256 íntegro")

patch_dirs = list(ROOT.glob("PATCH_Painel_Motoristas_*"))
ok("Pacote não depende de pasta de patch", not patch_dirs, f"{len(patch_dirs)} pasta(s) encontrada(s)")

print()
if FAILURES:
    print("BUILD V0.3.0.10: FALHA")
    print("Itens com falha: " + ", ".join(FAILURES))
    sys.exit(1)

print("BUILD V0.3.0.10: PASS")
print("Este ZIP já é completo; não aplique patches antigos sobre ele.")
