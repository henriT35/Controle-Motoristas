from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.core.performance import build_performance_score, build_performance_v3_score, percent, sample_confidence


def main():
    assert percent(15, 300) == Decimal("5.00")
    assert percent(8, 50) == Decimal("16.00")
    assert percent(8, 50) > percent(15, 300)
    assert sample_confidence(5, 30) == "LOW"
    assert sample_confidence(30, 30) == "MEDIUM"
    assert sample_confidence(90, 30) == "HIGH"

    clean = build_performance_score(
        success_rate=98, clean_rate=90, retention_rate=2, time_window_rate=1,
        overdue_proof_rate=0, recovery_rate=0, weights=None,
    )
    worse = build_performance_score(
        success_rate=80, clean_rate=55, retention_rate=16, time_window_rate=10,
        overdue_proof_rate=50, recovery_rate=0, weights=None,
    )
    assert clean.score > worse.score
    assert clean.score <= Decimal("100")
    assert worse.score >= Decimal("0")
    assert set(clean.breakdown) == {"delivery", "clean", "retention", "time_window", "proofs", "recovery"}

    # V3: uma nota oficial, pesos 50/35/15 e sem produtividade bruta.
    v3 = build_performance_v3_score(
        success_rate=72, primary_issue_rate=10, overdue_proof_rate=4,
        exact_recoveries=2, gold_recoveries=1, regularity_score=90,
    )
    v3_same_issue_different_success = build_performance_v3_score(
        success_rate=99, primary_issue_rate=10, overdue_proof_rate=4,
        exact_recoveries=2, gold_recoveries=1, regularity_score=90,
    )
    assert v3.score == v3_same_issue_different_success.score, "success não pode duplicar penalização da causa normalizada"
    assert v3.breakdown["proofs"]["weight"] == Decimal("50")
    assert v3.breakdown["quality"]["weight"] == Decimal("35")
    assert v3.breakdown["regularity"]["weight"] == Decimal("15")
    assert v3.bonus == Decimal("1.5"), "2 exatas (0,3) + 1 ouro (0,9)"
    capped = build_performance_v3_score(
        success_rate=100, primary_issue_rate=0, overdue_proof_rate=0,
        exact_recoveries=100, gold_recoveries=100, regularity_score=100,
    )
    assert capped.score == Decimal("100.0") and capped.bonus == Decimal("5.0")
    print(f"PERFORMANCE FORMULA QA: PASS — V2 limpo={clean.score}; V2 crítico={worse.score}; V3={v3.score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
