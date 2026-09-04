from pathlib import Path
import json
import sys

BASE = Path(__file__).resolve().parents[2]
required = [
    "Dockerfile", "Dockerfile.robot", "docker-compose.yml", ".env.vps.example",
    "deploy/nginx/default.conf", "deploy/vps/install.sh", "deploy/vps/update.sh",
    "scripts/docker/web-entrypoint.sh", "scripts/docker/robot-entrypoint.sh",
    "whatsapp_bridge/Dockerfile",
]
missing = [p for p in required if not (BASE / p).exists()]
if missing:
    raise SystemExit("Arquivos VPS ausentes: " + ", ".join(missing))

compose = (BASE / "docker-compose.yml").read_text(encoding="utf-8")
for service in ("web:", "db:", "redis:", "worker:", "beat:", "robot-worker:", "whatsapp:", "nginx:"):
    if service not in compose:
        raise SystemExit(f"Serviço Docker ausente: {service}")
if "restart: unless-stopped" not in compose:
    raise SystemExit("Boot automático Docker não configurado")
if 'SSW_ROBOT_DISPATCH_MODE: celery' not in compose:
    raise SystemExit("Robô SSW não está roteado para Celery na VPS")
if 'WHATSAPP_BRIDGE_EXTERNAL_SERVICE: "1"' not in compose:
    raise SystemExit("Bridge Baileys externo não configurado")

pkg = json.loads((BASE / "whatsapp_bridge/package.json").read_text(encoding="utf-8"))
if not pkg.get("dependencies", {}).get("@whiskeysockets/baileys"):
    raise SystemExit("Baileys ausente do package.json")

print("VPS_STATIC_QA=PASS")
