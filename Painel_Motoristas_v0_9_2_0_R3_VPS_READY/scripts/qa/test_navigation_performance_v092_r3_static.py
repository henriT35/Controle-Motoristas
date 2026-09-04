from pathlib import Path


def text(path):
    return Path(path).read_text(encoding="utf-8")

warm = text("apps/core/warmup.py")
ops = text("apps/operations/views.py")
diag = text("scripts/windows/performance-diagnostico.ps1")
online = text("scripts/windows/start-online.ps1")
local = text("scripts/windows/start-native.ps1")

assert "def _period_for_mode" in warm
assert "settings_obj.period_default" in warm
assert "_evolution_payload(period_start, period_end)" in warm
assert '"graph_points"' in warm
assert '"cte__retained_proof"' in ops
assert "delivered_ids.intersection(filtered_cte_ids)" in ops
assert "PERF session.start" in online
assert "PERF session.start" in local
assert "DESTA SESSAO" in diag
assert "Resumo por tela DESTA SESSAO" in diag
print("NAVIGATION PERFORMANCE R3 STATIC QA: PASS")
