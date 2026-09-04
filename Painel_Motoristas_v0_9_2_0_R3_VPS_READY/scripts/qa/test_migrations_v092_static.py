from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    path = ROOT / rel
    assert path.is_file(), f"arquivo ausente: {rel}"
    return path.read_text(encoding="utf-8", errors="replace")


def require(text: str, needles: list[str], label: str) -> None:
    missing = [item for item in needles if item not in text]
    assert not missing, f"{label}: ausente(s): {missing}"


core_model = read("apps/core/models.py")
core_mig = read("apps/core/migrations/0003_v0_9_2_0_evaluation_settings.py")
drivers_model = read("apps/drivers/models.py")
drivers_mig = read("apps/drivers/migrations/0003_v0_9_2_0_quality_events.py")
proofs_model = read("apps/proofs/models.py")
proofs_mig = read("apps/proofs/migrations/0003_v0_9_2_0_opportunities_and_ssw_state.py")

require(core_model, [
    "driver_v3_regularity_window_days",
    "driver_v3_actions_activation_date",
], "core model")
require(core_mig, [
    'name="driver_v3_regularity_window_days"',
    'name="driver_v3_actions_activation_date"',
], "core migration")

require(drivers_model, [
    "class DriverQualityEvent",
    "class DriverScoreSnapshot",
    'name="uniq_quality_event_movement_code"',
    'name="drivers_qe_status_date_idx"',
    'name="drivers_qe_driver_date_idx"',
    'name="uniq_driver_score_snapshot_period"',
    'name="drivers_score_driver_date_idx"',
], "drivers model")
require(drivers_mig, [
    'name="DriverQualityEvent"',
    'name="DriverScoreSnapshot"',
    'name="uniq_quality_event_movement_code"',
    'name="drivers_qe_status_date_idx"',
    'name="drivers_qe_driver_date_idx"',
    'name="uniq_driver_score_snapshot_period"',
    'name="drivers_score_driver_date_idx"',
], "drivers migration")

require(proofs_model, [
    "class ProofPickupOpportunity",
    "class ProofRetentionObligation",
    'TRACKING = "ACOMPANHANDO_SSW"',
    'name="uniq_pickup_opportunity_day"',
    'name="proofs_opp_drv_date_kind_idx"',
    'name="proofs_opp_status_date_idx"',
    'name="uniq_retention_obligation_attempt"',
    'name="proofs_retobl_driver_date_idx"',
    'name="proofs_retobl_status_date_idx"',
], "proofs model")
require(proofs_mig, [
    'name="ProofPickupOpportunity"',
    'name="ProofRetentionObligation"',
    'name="resolution_source"',
    'name="last_ssw_code"',
    'name="last_ssw_description"',
    'name="last_ssw_at"',
    'name="uniq_pickup_opportunity_day"',
    'name="proofs_opp_drv_date_kind_idx"',
    'name="proofs_opp_status_date_idx"',
    'name="uniq_retention_obligation_attempt"',
    'name="proofs_retobl_driver_date_idx"',
    'name="proofs_retobl_status_date_idx"',
], "proofs migration")

# Regressão do problema v0.9.1.0: índices versionados não podem voltar a nomes
# automáticos implícitos em models.py.
for rel, names in {
    "apps/drivers/models.py": ["drivers_dri_status_e3c5d8_idx", "drivers_dri_driver__4f7925_idx"],
    "apps/proofs/models.py": [
        "proofs_reta_status_9c7988_idx", "proofs_reta_client__1567c0_idx",
        "proofs_reta_origina_855a85_idx", "proofs_proo_status_aeb59b_idx",
        "proofs_proo_driver__bc6882_idx", "proofs_proo_driver__05b467_idx",
        "proofs_proo_driver__077d69_idx", "proofs_proo_proof_i_d8cc8e_idx",
    ],
}.items():
    require(read(rel), [f'name="{name}"' for name in names], f"index names {rel}")

# Boot scripts não devem criar migrations automaticamente em produção/local.
for rel in ["scripts/docker/web-entrypoint.sh", "scripts/windows/start-native.ps1", "scripts/windows/start-online.ps1"]:
    text = read(rel).lower()
    assert "makemigrations --check" in text, f"{rel}: validação --check ausente"
    # Aceita o comando de check, mas não um makemigrations de criação silenciosa.
    lines = [line.strip() for line in text.splitlines() if "makemigrations" in line and not line.strip().startswith("#")]
    assert all("--check" in line for line in lines), f"{rel}: makemigrations sem --check: {lines}"

print("MIGRATIONS V0.9.2 STATIC QA: PASS — modelos/migrations/índices versionados alinhados por contrato estático")
