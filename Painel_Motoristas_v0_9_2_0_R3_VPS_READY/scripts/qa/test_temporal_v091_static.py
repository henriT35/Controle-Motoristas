"""Contrato estático das regressões temporais críticas da v0.9.1.0.

Não substitui django.test com relatórios reais. Garante que as regressões permanentes
exigidas continuam presentes na suíte e que os pontos de implementação não foram
silenciosamente removidos durante empacotamento/refactor.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ssw_tests = (ROOT / "apps/ssw/tests.py").read_text(encoding="utf-8")
ops_tests = (ROOT / "apps/operations/tests.py").read_text(encoding="utf-8")
engine = (ROOT / "apps/ssw/import_engine_v2.py").read_text(encoding="utf-8")
services = (ROOT / "apps/core/services.py").read_text(encoding="utf-8")

required_ssw_tests = [
    "test_rom34_beats_repeated_ctrc34_when_choosing_origin_attempt",
    "test_nonconclusive_ctrc_status_after_rom34_goes_to_tracking",
    "test_tracking_becomes_recovered_when_current_ctrc_is_delivered",
    "test_rom34_without_date_uses_historical_manifest_not_import_time",
]
required_ops_tests = [
    "test_later_rom_event_does_not_migrate_old_manifest_to_new_day",
    "test_ctrc_consolidated_event_never_infers_route_date",
    "test_same_cte_multiple_attempts_keep_independent_manifest_dates",
    "test_time_window_failure_closes_old_attempt_and_live_ctrc85_selects_only_new_attempt",
    "test_undated_rom_fact_can_be_reconstructed_from_unique_same_ctrc_fact",
    "test_reconstruction_refuses_same_event_shared_by_two_attempts",
]
for name in required_ssw_tests:
    assert name in ssw_tests, f"regressão SSW ausente: {name}"
for name in required_ops_tests:
    assert name in ops_tests, f"regressão temporal ausente: {name}"

for code in ('("60", "DOCUMENTOS")', '("53", "AVARIA")', '("91", "INDENIZACAO")'):
    assert code in ssw_tests, f"caso ambíguo ausente: {code}"

assert "ROM34" in engine and "SEMPRE vence CTRC34" in engine
assert "tracking_state" in engine and "RetainedProof.Status.TRACKING" in engine
assert "ROM85" in services and "CTRC85" in services
assert "tentativa" in services.lower()

print("TEMPORAL STATIC QA: PASS — ROM85/ROM34/13/CTRC e 60/53/91 em acompanhamento automático presentes")
