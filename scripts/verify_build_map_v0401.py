from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import importlib.util
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.4.0.1"

REQUIRED = [
    "apps/operations/geo.py",
    "apps/operations/tests_geo.py",
    "templates/operations/map.html",
    "static/js/geo_map.js",
    "docs/MAPA_OPERACIONAL.md",
    "docs/MAPA_OPERACIONAL_ARQUITETURA.md",
    "docs/GEODADOS_FONTES.md",
    "docs/MAPA_OPERACIONAL_TESTES.md",
    "docs/BUGS_ENCONTRADOS_MAPA.md",
]


def ok(label):
    print(f"[OK] {label}")


def fail(label):
    print(f"[ERRO] {label}")
    return 1


def robot_core_ok():
    manifest = ROOT / "robot_ssw" / "HOMOLOGATED_CORE.sha256"
    if not manifest.exists():
        return False, "HOMOLOGATED_CORE.sha256 ausente"
    expected = {}
    for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            expected[parts[1].lstrip("*").replace("\\", "/")] = parts[0].lower()
    checked = 0
    for rel, digest in expected.items():
        path = ROOT / "robot_ssw" / rel
        if not path.exists():
            return False, f"core ausente: {rel}"
        actual = sha256(path.read_bytes()).hexdigest().lower()
        if actual != digest:
            return False, f"core alterado: {rel}"
        checked += 1
    return True, f"{checked} arquivo(s) do manifesto íntegros"


def run(cmd):
    print("$", " ".join(map(str, cmd)))
    return subprocess.run(cmd, cwd=ROOT).returncode


def main():
    errors = 0
    version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() if (ROOT / "VERSION.txt").exists() else ""
    if version == EXPECTED_VERSION:
        ok(f"VERSION {version}")
    else:
        errors += fail(f"VERSION={version!r}; esperado {EXPECTED_VERSION}")

    for rel in REQUIRED:
        if (ROOT / rel).exists():
            ok(rel)
        else:
            errors += fail(f"arquivo ausente: {rel}")

    bridge = (ROOT / "apps/ssw/robot_bridge.py").read_text(encoding="utf-8")
    if 'if unit != "BEL"' in bridge or 'esperado BEL.' in bridge:
        errors += fail("bridge ainda possui validação de unidade hardcoded em BEL")
    else:
        ok("bridge usa SSW_ROBOT_UNIT em vez de BEL hardcoded")

    geo = (ROOT / "apps/operations/geo.py").read_text(encoding="utf-8")
    forbidden = ['if branch == "BEL"', "if branch == 'BEL'", 'if branch == "CWB"', "if branch == 'CWB'"]
    if any(x in geo for x in forbidden):
        errors += fail("engine geográfica contém branch hardcoded")
    else:
        ok("engine sem hardcode de filial BEL/CWB")

    geo_js = (ROOT / "static/js/geo_map.js").read_text(encoding="utf-8")
    if "codarea" not in geo_js or "loadMunicipalityNames" not in geo_js:
        errors += fail("hotfix municipal codarea -> nome ausente no frontend")
    else:
        ok("hotfix municipal codarea -> nome presente")
    if "MUNICIPALITY_LOCALITIES_URL" not in geo or "locality_sources" not in geo:
        errors += fail("fonte oficial de Localidades IBGE não configurada")
    else:
        ok("Localidades IBGE configuradas por UF")

    core_ok, detail = robot_core_ok()
    if core_ok:
        ok("robot_ssw: " + detail)
    else:
        errors += fail("robot_ssw: " + detail)

    py_files = [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts and "__pycache__" not in p.parts]
    for path in py_files:
        try:
            compile(path.read_bytes(), str(path), "exec")
        except Exception as exc:
            errors += fail(f"Python inválido {path.relative_to(ROOT)}: {exc}")
            break
    else:
        ok(f"compile estático: {len(py_files)} arquivos Python")

    if importlib.util.find_spec("django") is None:
        print("[AVISO] Django não está disponível neste Python. Rode novamente após EXECUTAR_LOCAL.bat criar/preparar a .venv.")
    else:
        if run([sys.executable, "manage.py", "check"]) != 0:
            errors += fail("manage.py check")
        else:
            ok("manage.py check")
        if run([sys.executable, "manage.py", "test", "apps.operations.tests_geo", "--verbosity", "1"]) != 0:
            errors += fail("testes geográficos Django")
        else:
            ok("testes geográficos Django")

    if errors:
        print(f"\nBUILD V0.4.0.1: FAIL ({errors} problema(s))")
        return 1
    print("\nBUILD V0.4.0.1: PASS (validações disponíveis neste ambiente)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
