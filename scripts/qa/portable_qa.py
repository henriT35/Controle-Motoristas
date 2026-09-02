from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from apps.ssw.parsers import read_ssw_delivery_file, row_is_retained, row_route_exit_date, validate_delivery_row


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    results = []

    # Sintaxe Python de todo o projeto.
    py_files = list(ROOT.rglob("*.py"))
    syntax_errors = []
    for path in py_files:
        try:
            source = path.read_text(encoding="utf-8", errors="strict")
            compile(source, str(path), "exec")
        except Exception as exc:
            syntax_errors.append(f"{path.relative_to(ROOT)}: {exc}")
    results.append(("Sintaxe Python", not syntax_errors, f"{len(py_files)} arquivos; erros={len(syntax_errors)}"))

    # Core do robô não alterado.
    manifest = ROOT / "robot_ssw" / "HOMOLOGATED_CORE.sha256"
    core_failures = []
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            expected, rel = line.split(None, 1)
            target = ROOT / "robot_ssw" / rel.strip()
            if not target.exists() or sha256(target) != expected:
                core_failures.append(rel.strip())
    else:
        core_failures.append("manifest ausente")
    results.append(("Core homologado", not core_failures, "6/6 hashes OK" if not core_failures else ", ".join(core_failures)))

    # Engine deve possuir lock e fingerprint semântico.
    engine = (ROOT / "apps" / "ssw" / "import_engine_v2.py").read_text(encoding="utf-8")
    results.append(("Lock de importação", "SSWImportLock" in engine and "import_lock.acquire()" in engine, "serialização cross-processo"))
    results.append(("Fingerprint ocorrência", "_occurrence_identity" in engine and "normalize_text(description)" in engine, "descrição normalizada"))
    results.append(("Validação silenciosa removida", "validate_delivery_row" in engine, "número/data/hora inválidos viram WARNING/ignorado"))

    # A hotfix de identidade v0.3.0.10 usa get_or_create SOMENTE no loop
    # limitado a clientes novos. ORM continua proibido nos loops por linha.
    tree = ast.parse(engine)
    forbidden = []
    allowed_identity = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While)):
            continue
        iterator = ast.unparse(node.iter) if isinstance(node, ast.For) else "while"
        loop_calls = []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = ast.unparse(sub.func)
                if ".objects." in func or func.endswith(".save"):
                    loop_calls.append((getattr(sub, "lineno", 0), func))
        if not loop_calls:
            continue
        if iterator in {"new_clients", "promoted_clients.values()"}:
            allowed_identity.append((iterator, loop_calls))
        else:
            forbidden.append((iterator, loop_calls))
    results.append((
        "Engine v2 sem ORM no hot path",
        not forbidden,
        f"forbidden={forbidden}; identity_loops={len(allowed_identity)}",
    ))

    # Dataset real, quando estiver disponível ao lado do ambiente ChatGPT.
    candidate = Path("/mnt/data/CSVssw0146RVI[1]230259.sswweb")
    real = None
    if candidate.exists():
        parsed = read_ssw_delivery_file(candidate)
        ctes = {r.get("CTRC", "").strip() for r in parsed.rows if r.get("CTRC", "").strip()}
        retained = {r.get("CTRC", "").strip() for r in parsed.rows if r.get("CTRC", "").strip() and row_is_retained(r)}
        routes = {r.get("ROMANEIO", "").strip() for r in parsed.rows if row_route_exit_date(r)}
        invalid = [(i, validate_delivery_row(r)) for i, r in enumerate(parsed.rows, 1) if validate_delivery_row(r)]
        real = {
            "rows": len(parsed.rows), "ctes": len(ctes), "retained_ctes": len(retained),
            "route_manifests": len(routes), "invalid_rows": len(invalid),
            "period_start": str(parsed.period_start), "period_end": str(parsed.period_end),
        }
        results.append(("Dataset real parse", len(parsed.rows) == 2838 and len(ctes) == 2566 and len(retained) == 152, json.dumps(real, ensure_ascii=False)))
        results.append(("Dataset real validação", not invalid, f"linhas inválidas={len(invalid)}"))

    print("=" * 78)
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").exists() else "?"
    print(f"QA PORTÁTIL — PAINEL MOTORISTAS v{version}")
    print("=" * 78)
    failed = 0
    for name, ok, detail in results:
        if not ok:
            failed += 1
        print(f"{'PASS' if ok else 'FAIL':4} | {name:32} | {detail}")
    print("-" * 78)
    print(f"PASS={len(results)-failed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
