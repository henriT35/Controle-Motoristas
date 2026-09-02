from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.core.performance import build_performance_score, percent, sample_confidence


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
    print(f"PERFORMANCE FORMULA QA: PASS — cenário limpo={clean.score}; cenário crítico={worse.score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
