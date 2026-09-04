from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def require(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main():
    drivers_models = text("apps/drivers/models.py")
    evaluation = text("apps/drivers/evaluation.py")
    core_services = text("apps/core/services.py")
    proofs_models = text("apps/proofs/models.py")
    proofs_services = text("apps/proofs/services.py")
    portal = text("apps/drivers/portal_views.py")
    parser = text("apps/ssw/parsers.py")
    engine = text("apps/ssw/import_engine_v2.py")
    driver_migration = text("apps/drivers/migrations/0003_v0_9_2_0_quality_events.py")
    proof_migration = text("apps/proofs/migrations/0003_v0_9_2_0_opportunities_and_ssw_state.py")
    core_migration = text("apps/core/migrations/0003_v0_9_2_0_evaluation_settings.py")

    # Qualidade: ROM13 é evento manual por tentativa; pendente não afeta.
    require("class DriverQualityEvent" in drivers_models, "DriverQualityEvent ausente")
    require('DRIVER_RESPONSIBLE = "DRIVER_RESPONSIBLE"' in drivers_models, "status de responsabilidade ausente")
    require('UniqueConstraint(fields=["movement", "code"]' in drivers_models, "idempotência ROM13 por tentativa ausente")
    require("return self.status == self.Status.DRIVER_RESPONSIBLE" in drivers_models, "PENDING pode estar afetando qualidade")
    require('Q(code="13")' in evaluation and "ENTREGA PREJUDICADA PELO HORARIO" in evaluation, "materialização ROM13 ausente")
    require("if status == DriverQualityEvent.Status.DRIVER_RESPONSIBLE and not visible_reason" in evaluation, "motivo visível obrigatório ausente")
    require('quality_failure_rate = percent(qstats["responsible"], evaluation_attempts)' in core_services, "qualidade não proporcional às tentativas da janela V3")
    require('quality_failure_rate=quality_failure_rate' in core_services, "V3 não recebe taxa de ROM13 validado")

    # ROM34 não volta como punição V3: o raw histórico pode existir em estatísticas,
    # mas a taxa enviada ao V3 deve vir exclusivamente de quality_stats.
    require('qstats = quality_stats[driver_id]' in core_services, "quality_stats manual ausente")
    require('primary_issue_rate=quality_failure_rate' in core_services, "V3 ainda usa primary_issues ROM34/ROM13 bruto")

    # Regularidade: ação exigida respondida / exigida; GOLD nunca entra no denominador.
    require("class ProofPickupOpportunity" in proofs_models, "persistência de oportunidade ausente")
    require('kind=ProofPickupOpportunity.Kind.EXACT' in core_services, "Regularidade não filtra EXACT")
    regularity_block = core_services[core_services.index("regularity_stats ="):core_services.index("proof_management_stats =")]
    require("Kind.GOLD" not in regularity_block, "GOLD está entrando na Regularidade")
    require("ProofRetentionObligation" in regularity_block, "ressalva obrigatória não entra na Regularidade")
    require("driver_v3_actions_activation_date" in evaluation, "marco prospectivo de ações ausente")
    require('ProofPickupOpportunity.Status.EXPIRED_NEUTRAL' in evaluation, "GOLD não expira de forma neutra")

    # Portal: respostas neutras precisam de observação/justificativa e projeção usa fórmula oficial.
    require("NOT_RELEASED" in portal and "UNABLE" in portal, "ações de retirada ausentes")
    require("Ainda não liberado" in portal or "ainda não liberado" in portal.lower(), "regra de não liberado ausente")
    require("build_performance_v3_score" in portal and "projected_position" in portal, "projeção de ranking não usa fórmula V3")
    require("present_pickup_opportunities" in portal, "oportunidade apresentada não é persistida")

    # Retenção: estado atual governa. ENTREGUE resolve sem inventar recuperação.
    require('TRACKING = "ACOMPANHANDO_SSW"' in proofs_models, "estado ACOMPANHANDO_SSW ausente")
    require("current_description = clean(proof.cte.current_status)" in proofs_services, "reconciliação não usa current_status")
    require("is_delivered_occurrence(code, description)" in proofs_services, "ENTREGUE não resolve na reconciliação")
    require('proof.recovery_driver = None' in proofs_services, "auto resolução não limpa/inibe recovery_driver")
    require('proof.resolution_source = "SSW"' in proofs_services, "origem automática SSW não registrada")
    require("delivered_after_retention = bool(historically_retained and delivered)" in parser, "parser ainda depende de cronologia para ENTREGUE")
    require("effective_ctrc_snapshot" in engine and "snapshot_operational_date < latest_known_date" in engine, "proteção de snapshot fora de ordem ausente")

    # Migrations formais e nomes explícitos.
    require("DriverQualityEvent" in driver_migration and "DriverScoreSnapshot" in driver_migration, "migration drivers incompleta")
    require("ProofPickupOpportunity" in proof_migration and "ProofRetentionObligation" in proof_migration, "migration proofs incompleta")
    require("driver_v3_regularity_window_days" in core_migration and "driver_v3_actions_activation_date" in core_migration, "migration core incompleta")
    for idx in [
        "drivers_qe_status_date_idx", "drivers_qe_driver_date_idx", "drivers_score_driver_date_idx",
        "proofs_opp_drv_date_kind_idx", "proofs_opp_status_date_idx", "proofs_retobl_driver_date_idx", "proofs_retobl_status_date_idx",
    ]:
        require(idx in drivers_models + proofs_models, f"índice model ausente: {idx}")
        require(idx in driver_migration + proof_migration, f"índice migration ausente: {idx}")

    print("V0.9.2 CONTRACT STATIC QA: PASS — ROM13 manual, Regularidade real, Portal explicável e retenção por estado atual")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"V0.9.2 CONTRACT STATIC QA: FAIL — {exc}")
        raise
