from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = [
    "apps/core/migrations/0001_initial.py",
    "apps/core/migrations/0002_v0_9_1_0_ranking_v3.py",
    "apps/drivers/migrations/0001_initial.py",
    "apps/drivers/migrations/0002_v0_9_1_0_portal_access_requests.py",
    "apps/proofs/migrations/0001_initial.py",
    "apps/proofs/migrations/0002_v0_9_1_0_portal_proofs.py",
    "apps/operations/migrations/0001_initial.py",
    "apps/ssw/migrations/0001_initial.py",
    "apps/messaging/migrations/0001_initial.py",
]


def main():
    missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
    assert not missing, f"migrations ausentes: {missing}"

    core2 = (ROOT / REQUIRED[1]).read_text(encoding="utf-8")
    drivers2 = (ROOT / REQUIRED[3]).read_text(encoding="utf-8")
    proofs2 = (ROOT / REQUIRED[5]).read_text(encoding="utf-8")
    assert "driver_v3_proofs_weight" in core2 and "top3_reward_description" in core2
    assert "DriverPortalAccessRequest" in drivers2
    assert "ProofRetention" in proofs2 and "ProofPickupAttempt" in proofs2

    boot_files = [
        ROOT / "scripts/docker/web-entrypoint.sh",
        ROOT / "scripts/windows/start-native.ps1",
        ROOT / "scripts/windows/start-online.ps1",
        ROOT / "scripts/windows/import-native.ps1",
        ROOT / "scripts/windows/import-batch-native.ps1",
    ]
    for path in boot_files:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "makemigrations" in line and not line.lstrip().startswith("#"):
                assert "--check" in line, f"{path}: makemigrations de criação automática: {line}"
    entry = (ROOT / "scripts/docker/web-entrypoint.sh").read_text(encoding="utf-8")
    assert "migrate --fake-initial --noinput" in entry

    # Regression: index names must be explicit in models and identical to the
    # already-versioned migrations. Otherwise Django may propose RenameIndex
    # migrations only because the auto-generated name algorithm/state differs.
    index_contract = {
        "apps/bugs/models.py": [
            "bugs_bugrep_screen_829032_idx", "bugs_bugrep_priorit_5246d2_idx",
        ],
        "apps/drivers/models.py": [
            "drivers_dri_status_e3c5d8_idx", "drivers_dri_driver__4f7925_idx",
        ],
        "apps/messaging/models.py": [
            "messaging_w_status_36a147_idx", "messaging_w_operati_7db751_idx",
        ],
        "apps/operations/models.py": [
            "operations__movemen_0bba38_idx", "operations__movemen_df1979_idx",
            "operations__code_941cf6_idx", "operations__cte_id_625e3d_idx",
            "operations__movemen_80321e_idx",
        ],
        "apps/proofs/models.py": [
            "proofs_reta_status_9c7988_idx", "proofs_reta_client__1567c0_idx",
            "proofs_reta_origina_855a85_idx", "proofs_proo_status_aeb59b_idx",
            "proofs_proo_driver__bc6882_idx", "proofs_proo_driver__05b467_idx",
            "proofs_proo_driver__077d69_idx", "proofs_proo_proof_i_d8cc8e_idx",
        ],
        "apps/reports/models.py": ["reports_gen_report__7f56d9_idx"],
        "apps/ssw/models.py": [
            "ssw_importr_status_140239_idx", "ssw_importr_kind_816ee4_idx",
        ],
    }
    for rel, names in index_contract.items():
        model_text = (ROOT / rel).read_text(encoding="utf-8")
        for name in names:
            assert f'name="{name}"' in model_text, f"{rel}: index versionado sem nome explícito {name}"

    print("MIGRATIONS V0.9.1 STATIC QA: PASS — migrations formais, índices estáveis e boot sem criação automática")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
