from __future__ import annotations

import hashlib
import json
import py_compile
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.ssw.diagnostics import (  # noqa: E402
    DiagnosticRecorder,
    RunContext,
    build_diagnostic_zip,
    pause_queue,
    queue_pause_state,
    resume_queue,
    sanitize,
    write_worker_state,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS | {message}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    check((ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "0.3.0.4", "VERSION 0.3.0.4")
    check(not (ROOT / "Painel_Motoristas_v0_3_0_3_COMPLETO").exists(), "sem projeto duplicado aninhado")

    dispatch = (ROOT / "apps/ssw/dispatch.py").read_text(encoding="utf-8")
    check('"run_ssw_robot_guarded"' in dispatch, "dispatch usa watchdog")
    check("check_robot_ready(launch_browser=False)" in dispatch, "Chromium não abre fora do watchdog")
    check("reconcile_orphan_runs" in dispatch, "reconciliação de jobs órfãos ativa")

    tasks = (ROOT / "apps/ssw/tasks.py").read_text(encoding="utf-8")
    check('call_command("run_ssw_robot_guarded"' in tasks, "Celery usa o mesmo watchdog")
    check("autoretry_for" not in tasks, "sem autoretry cego do robô")

    guarded = (ROOT / "apps/ssw/management/commands/run_ssw_robot_guarded.py").read_text(encoding="utf-8")
    check("execution_id_for(run)" in guarded, "watchdog usa execution_id real")
    check("result.json" in guarded and "_reported_error" in guarded, "erro real do robô é preservado")
    check("taskkill" in guarded, "encerramento da árvore de processos no Windows")

    views = (ROOT / "apps/ssw/views.py").read_text(encoding="utf-8")
    urls = (ROOT / "apps/ssw/urls.py").read_text(encoding="utf-8")
    imports_tpl = (ROOT / "templates/ssw/imports.html").read_text(encoding="utf-8")
    history_tpl = (ROOT / "templates/ssw/history.html").read_text(encoding="utf-8")
    check('and not pause_state.get("paused")' in views, "polling encerra quando a fila pausa")
    check("ssw_queue_resume" in urls and "ssw_retry_failed" in urls and "ssw_diagnostic_download" in urls, "rotas de retomada/retry/diagnóstico")
    check("Fila SSW pausada" in imports_tpl and "Retomar fila" in imports_tpl, "banner de pausa na tela de importações")
    check("Reprocessar somente esta janela" in history_tpl and "Baixar diagnóstico técnico" in history_tpl, "controles de recuperação no histórico")

    safe = sanitize("senha=abc token=xyz cookie=qwe")
    check("abc" not in safe and "xyz" not in safe and "qwe" not in safe, "sanitização de segredos")

    with tempfile.TemporaryDirectory(prefix="qa_v0304_") as tmp:
        base = Path(tmp)
        pause_queue(base, reason="teste", execution_id="SSW-QA", error_code="QA")
        check(queue_pause_state(base).get("paused") is True, "marcador de pausa persistente")
        resume_queue(base)
        check(not queue_pause_state(base).get("paused"), "retomada remove marcador de pausa")

        run_dir = base / "imports" / "inbox" / "SSW-QA"
        rec = DiagnosticRecorder(run_dir, RunContext(execution_id="SSW-QA", run_pk="1", app_version="0.3.0.4"))
        rec.event("QA_EVENT", stage="TEST", message="senha=nao-vazar")
        write_worker_state(run_dir, status="RUNNING", child_pid=123, last_heartbeat_at="2026-09-01T10:00:00-03:00")
        (run_dir / "relatorio_036.sswweb").write_text("DADO OPERACIONAL", encoding="utf-8")
        package = build_diagnostic_zip(base, "SSW-QA")
        with zipfile.ZipFile(package) as zf:
            names = set(zf.namelist())
            events = zf.read("events.jsonl").decode("utf-8")
        check("events.jsonl" in names and "worker_state.json" in names, "pacote diagnóstico contém timeline/heartbeat")
        check("relatorio_036.sswweb" not in names, "pacote diagnóstico não inclui relatório operacional")
        check("nao-vazar" not in events, "logs sanitizados")

    manifest = ROOT / "robot_ssw" / "HOMOLOGATED_CORE.sha256"
    expected = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            expected[parts[1].lstrip("*")] = parts[0].lower()
    for rel, digest in expected.items():
        path = ROOT / "robot_ssw" / rel
        check(path.exists() and sha256(path).lower() == digest, f"core homologado íntegro: {rel}")

    compiled = 0
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or ".venv" in path.parts:
            continue
        py_compile.compile(str(path), doraise=True)
        compiled += 1
    check(compiled > 0, f"sintaxe Python válida ({compiled} arquivos)")
    print("\nQA RESILIÊNCIA v0.3.0.4: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
