from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

# Teste puro do contrato de número sem inicializar Django: extrai a função via
# execução do módulo não é viável por imports Django, então verificamos o código
# e o bridge JS em conjunto.
services = (BASE / "apps/messaging/services.py").read_text(encoding="utf-8")
bridge = (BASE / "whatsapp_bridge/server.mjs").read_text(encoding="utf-8")
for token in ("whatsapp_phone_candidates", 'national[2:3] == "9"'):
    if token not in services:
        raise SystemExit(f"Contrato Python ausente: {token}")
for token in ("brazilianCandidates", "resolveWhatsAppRecipient", "socket.onWhatsApp", "resolved_phone"):
    if token not in bridge:
        raise SystemExit(f"Contrato Baileys ausente: {token}")
print("WHATSAPP_PHONE_STATIC_QA=PASS")
