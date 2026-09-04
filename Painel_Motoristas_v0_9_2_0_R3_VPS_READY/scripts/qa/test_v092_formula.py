from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from apps.core.performance import build_performance_v3_score, percent


def score_for(attempts, failures):
    failure_rate = percent(failures, attempts)
    return build_performance_v3_score(
        success_rate=100,
        primary_issue_rate=failure_rate,
        quality_failure_rate=failure_rate,
        proof_management_score=100,
        regularity_score=100,
        exact_recoveries=0,
        gold_recoveries=0,
        weights={"proofs": 50, "quality": 35, "regularity": 15},
    )


def main():
    a = score_for(50, 2)
    b = score_for(300, 12)
    c = score_for(300, 2)
    assert a.components["quality"] == Decimal("96.0")
    assert b.components["quality"] == Decimal("96.0")
    assert c.components["quality"] == Decimal("99.3")
    assert a.score == b.score, (a.score, b.score)
    assert c.score > b.score
    assert percent(18, 20) == Decimal("90.00")

    # Bônus é limitado e nunca empurra a nota acima de 100.
    capped = build_performance_v3_score(
        success_rate=100, primary_issue_rate=0, quality_failure_rate=0,
        proof_management_score=100, regularity_score=100,
        exact_recoveries=100, gold_recoveries=100,
        exact_bonus=Decimal("0.30"), gold_bonus=Decimal("0.90"), bonus_cap=Decimal("5.00"),
    )
    assert capped.bonus == Decimal("5.0")
    assert capped.score == Decimal("100.0")
    print(
        "V0.9.2 FORMULA QA: PASS — "
        f"50/2={a.components['quality']}%, 300/12={b.components['quality']}%, "
        f"300/2={c.components['quality']}%, regularidade 18/20=90%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
