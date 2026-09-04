from __future__ import annotations

import ast
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CANDIDATES = [
    ROOT / "CSVssw0146RVI[1]230259.sswweb",
    ROOT.parent / "CSVssw0146RVI[1]230259.sswweb",
]

# Loops de identidade nova/promovida são deliberadamente limitados pelo número
# de CLIENTES únicos do lote. A hotfix v0.3.0.10 usa get_or_create nesses loops
# para não reintroduzir a colisão UNIQUE (cnpj, name). O que permanece proibido
# é ORM dentro do hot path que percorre cada linha preparada do relatório.
ALLOWED_IDENTITY_LOOPS = {"new_clients", "promoted_clients.values()"}


def load_parser():
    path = ROOT / "apps" / "ssw" / "parsers.py"
    spec = importlib.util.spec_from_file_location("performance_parser", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def orm_calls_inside_hot_loops(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    allowed = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While)):
            continue
        iterator = ast.unparse(node.iter) if isinstance(node, ast.For) else "while"
        loop_calls = []
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            func = ast.unparse(sub.func)
            if ".objects." in func or func.endswith(".save"):
                loop_calls.append((getattr(sub, "lineno", 0), func))
        if not loop_calls:
            continue
        if iterator in ALLOWED_IDENTITY_LOOPS:
            allowed.append((node.lineno, iterator, loop_calls))
        else:
            found.append((node.lineno, iterator, loop_calls))
    return found, allowed


def main():
    parser = load_parser()
    v2 = ROOT / "apps" / "ssw" / "import_engine_v2.py"
    hot_calls, identity_calls = orm_calls_inside_hot_loops(v2)
    assert not hot_calls, f"ORM dentro de hot loop do Import Engine v2: {hot_calls}"
    text = v2.read_text(encoding="utf-8")
    assert "bulk_create" in text and "bulk_update" in text
    assert "transaction.atomic" in text
    assert "Client.objects.get_or_create" in text, "Hotfix de identidade do cliente ausente"

    sample = next((p for p in SAMPLE_CANDIDATES if p.exists()), None)
    if sample:
        t0 = time.perf_counter()
        parsed = parser.read_ssw_delivery_file(sample)
        elapsed = time.perf_counter() - t0
        assert parsed.rows, "Amostra SSW sem linhas"
        print(f"Parser: {len(parsed.rows)} linhas em {elapsed:.4f}s")
    else:
        print("Parser: amostra SSW não incluída no pacote; teste de arquivo ignorado.")
    print("Import Engine v2: hot path por linha sem ORM; persistência bulk/transaction presente.")
    print(f"Loops ORM permitidos e limitados a identidades únicas: {[(x[1], len(x[2])) for x in identity_calls]}")
    print("STATIC PERFORMANCE QA: PASS")


if __name__ == "__main__":
    main()
