from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSERS = ROOT / "apps" / "ssw" / "parsers.py"
ENGINE = ROOT / "apps" / "ssw" / "import_engine_v2.py"
IMPORTER = ROOT / "apps" / "ssw" / "importer.py"

spec = importlib.util.spec_from_file_location("ssw_parsers_qa", PARSERS)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def row(**values):
    base = {
        "COD OCORR ROM": "",
        "DESC OCORR ROM": "",
        "DATA OCORR ROM": "",
        "HORA OCORR ROM": "",
        "COD OCORR CTRC": "",
        "DESC OCORR CTRC": "",
        "DATA OCORR CTRC": "",
        "HORA OCORR CTRC": "",
    }
    base.update(values)
    return base


# Caso real do relatório: ROM=34 sem data, mas CTRC já ENTREGUE depois.
s = module.retention_snapshot(row(**{
    "COD OCORR ROM": "34",
    "DESC OCORR ROM": "MERCADORIA EM CONFERENCIA NO CLIENTE",
    "COD OCORR CTRC": "1",
    "DESC OCORR CTRC": "ENTREGUE",
    "DATA OCORR CTRC": "20/05/2026",
    "HORA OCORR CTRC": "17:00",
}))
assert s.historically_retained is True
assert s.active_retention is False
assert s.delivered_after_retention is True
assert s.explicit_retained_at is None
assert s.recovered_at.strftime("%Y-%m-%d %H:%M") == "2026-05-20 17:00"

# Retenção realmente ativa: CTRC também continua no 34.
s = module.retention_snapshot(row(**{
    "COD OCORR ROM": "34",
    "DESC OCORR ROM": "MERCADORIA EM CONFERENCIA NO CLIENTE",
    "DATA OCORR ROM": "02/04/2026",
    "HORA OCORR ROM": "16:00",
    "COD OCORR CTRC": "34",
    "DESC OCORR CTRC": "MERCADORIA EM CONFERENCIA NO CLIENTE",
    "DATA OCORR CTRC": "02/04/2026",
    "HORA OCORR CTRC": "16:00",
}))
assert s.historically_retained is True
assert s.active_retention is True
assert s.delivered_after_retention is False
assert s.explicit_retained_at.strftime("%Y-%m-%d %H:%M") == "2026-04-02 16:00"

# Entrega normal nunca cria retenção.
s = module.retention_snapshot(row(**{
    "COD OCORR ROM": "1", "DESC OCORR ROM": "ENTREGUE",
    "COD OCORR CTRC": "1", "DESC OCORR CTRC": "ENTREGUE",
    "DATA OCORR CTRC": "02/04/2026", "HORA OCORR CTRC": "16:00",
}))
assert s.historically_retained is False
assert s.active_retention is False

engine_text = ENGINE.read_text(encoding="utf-8")
importer_text = IMPORTER.read_text(encoding="utf-8")
assert "proof-state-reconciliation" in engine_text
assert 'clean(o.source).upper() == "SSW_CTRC"' in engine_text
assert 'Baixa automática' in engine_text
assert 'retained_at or now' not in engine_text
assert 'source="SSW_CTRC"' in importer_text
assert 'Baixa automática' in importer_text

print("QA RETENCAO/BAIXA SSW v0.3.0.8: PASS")
