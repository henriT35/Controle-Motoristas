from __future__ import annotations

import ast
import importlib
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def ast_ok(rel: str) -> None:
    ast.parse(text(rel), filename=rel)


def main() -> int:
    guarded = text("apps/ssw/management/commands/run_ssw_robot_guarded.py")
    service = text("apps/ssw/robot_service.py")
    progress = text("apps/ssw/progress.py")
    settings = text("config/settings.py")
    dispatch = text("apps/ssw/dispatch.py")
    engine = text("apps/ssw/import_engine_v2.py")

    for rel in [
        "apps/ssw/management/commands/run_ssw_robot_guarded.py",
        "apps/ssw/robot_service.py",
        "apps/ssw/progress.py",
        "config/settings.py",
    ]:
        ast_ok(rel)

    require('read_import_progress' in guarded, "watchdog não lê progresso do importador")
    require('timeout_domain = "ROBOT"' in guarded, "domínio ROBOT ausente")
    require('timeout_domain = "IMPORT"' in guarded, "troca para domínio IMPORT ausente")
    require('str(robot_stage or "").upper() == "DOWNLOADED"' in guarded, "fronteira DOWNLOADED ausente")
    require('IMPORT_HARD_TIMEOUT' in guarded, "código IMPORT_HARD_TIMEOUT ausente")
    require('ROBOT_HARD_TIMEOUT' in guarded, "código ROBOT_HARD_TIMEOUT ausente")
    require('import_timeout_seconds=import_timeout' in guarded, "timeout do importador não vai ao diagnóstico")
    require('event_name = "IMPORT_PROGRESS"' in guarded, "evento IMPORT_PROGRESS ausente")
    require('effective_final_stage' in guarded, "estágio final do importador não é preservado")

    require('SSW_IMPORT_TIMEOUT_SECONDS' in settings and '"3600"' in settings, "timeout padrão de importação não configurado")
    require('clear_import_progress(run.pk)' in service, "snapshot antigo não é limpo")
    require('phase="Validação"' in service, "fronteira do Import Engine não publica progresso")
    require('IMPORT_ENGINE_ERROR' in service, "erro estruturado do importador ausente")
    require('ROBOT_UNEXPECTED' in service, "erro inesperado do robô ausente")
    require('resilient_atomic_json_write' in progress and 'best_effort=True' in progress, "progresso não usa escrita resiliente")
    require('def clear_import_progress' in progress, "clear_import_progress ausente")

    # Regressões conhecidas de releases anteriores continuam protegidas.
    require('def dispatch_robot_run(run_id: int, *, priority: bool = False)' in dispatch, "priority do v0.3.0.7 regrediu")
    require('0.3.0.8-proof-state-reconciliation' in engine, "regra de retenção v0.3.0.8 não está presente")
    require('retention_snapshot' in engine and 'SSW_CTRC' in engine, "estado consolidado CTRC não encontrado")

    # Smoke test real do arquivo de progresso sem Django instalado: injeta apenas settings.BASE_DIR.
    fake_django = types.ModuleType("django")
    fake_conf = types.ModuleType("django.conf")
    with tempfile.TemporaryDirectory(prefix="qa_v0309_") as td:
        fake_conf.settings = types.SimpleNamespace(BASE_DIR=td)
        sys.modules.setdefault("django", fake_django)
        sys.modules["django.conf"] = fake_conf
        sys.path.insert(0, str(ROOT))
        try:
            mod = importlib.import_module("apps.ssw.progress")
            mod.publish_import_progress(999, phase="Banco · CT-es", message="teste", percent=62, current=10, total=20)
            snap = mod.read_import_progress(999)
            require(bool(snap), "snapshot não foi escrito")
            require(snap.get("phase") == "Banco · CT-es", "fase do snapshot incorreta")
            require(float(snap.get("percent")) == 62.0, "percentual incorreto")
            mod.clear_import_progress(999)
            require(mod.read_import_progress(999) is None, "snapshot antigo não foi removido")
        finally:
            try:
                sys.path.remove(str(ROOT))
            except ValueError:
                pass

    print("QA WATCHDOG/IMPORT v0.3.0.9: PASS")
    print("- timeout ROBOT separado de IMPORT: OK")
    print("- DOWNLOADED troca domínio do watchdog: OK")
    print("- progresso do Import Engine observado: OK")
    print("- escrita de progresso resiliente/best-effort: OK")
    print("- retry priority v0.3.0.7 preservado: OK")
    print("- retenção CTRC v0.3.0.8 preservada: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
