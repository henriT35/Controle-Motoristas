from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from apps.ssw.parsers import clean, read_ssw_delivery_file, retention_snapshot

TARGETS = {"BNU046259-4", "CWB055520-7"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default="/mnt/data/qa_real_v092")
    args = parser.parse_args()
    base = Path(args.root)
    files = sorted(base.rglob("*.sswweb")) if base.exists() else []
    if not files:
        print(f"REAL RETENTION V0.9.2 QA: SKIP — nenhum .sswweb em {base}")
        return 0

    found = {}
    total_rows = 0
    for path in files:
        parsed = read_ssw_delivery_file(path)
        total_rows += len(parsed.rows)
        for row in parsed.rows:
            ctrc = clean(row.get("CTRC"))
            if ctrc not in TARGETS or ctrc in found:
                continue
            snap = retention_snapshot(row)
            found[ctrc] = {
                "file": str(path),
                "rom_code": clean(row.get("COD OCORR ROM")),
                "rom_desc": clean(row.get("DESC OCORR ROM")),
                "rom_date": clean(row.get("DATA OCORR ROM")),
                "rom_time": clean(row.get("HORA OCORR ROM")),
                "ctrc_code": clean(row.get("COD OCORR CTRC")),
                "ctrc_desc": clean(row.get("DESC OCORR CTRC")),
                "historically_retained": snap.historically_retained,
                "active_retention": snap.active_retention,
                "delivered_after_retention": snap.delivered_after_retention,
                "explicit_retained_at": snap.explicit_retained_at,
                "recovered_at": snap.recovered_at,
            }

    missing = TARGETS - set(found)
    if missing:
        raise AssertionError(f"casos reais não encontrados: {sorted(missing)}")

    bnu = found["BNU046259-4"]
    assert bnu["historically_retained"] is True
    assert bnu["ctrc_code"] == "1" and "ENTREGUE" in bnu["ctrc_desc"].upper()
    assert bnu["explicit_retained_at"] is None, "BNU deveria cobrir ROM34 sem data real"
    assert bnu["active_retention"] is False
    assert bnu["delivered_after_retention"] is True

    cwb = found["CWB055520-7"]
    assert cwb["historically_retained"] is True
    assert cwb["ctrc_code"] == "1" and "ENTREGUE" in cwb["ctrc_desc"].upper()
    assert cwb["explicit_retained_at"] is not None
    assert cwb["recovered_at"] is not None
    # Caso real importante: SSW corrigiu a entrega para uma data anterior ao ROM34.
    assert cwb["recovered_at"] < cwb["explicit_retained_at"], "CWB deveria cobrir cronologia retrocorrigida"
    assert cwb["active_retention"] is False
    assert cwb["delivered_after_retention"] is True

    print(f"REAL RETENTION V0.9.2 QA: PASS — {len(files)} relatórios, {total_rows} linhas")
    for ctrc in sorted(found):
        item = found[ctrc]
        print(
            f"PASS | {ctrc} | ROM34 histórico={item['historically_retained']} | "
            f"CTRC={item['ctrc_code']} {item['ctrc_desc']} | ativo={item['active_retention']} | "
            f"resolvido={item['delivered_after_retention']}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"REAL RETENTION V0.9.2 QA: FAIL — {exc}")
        raise
