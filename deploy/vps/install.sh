#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker não encontrado. Em Ubuntu/Hostinger instale Docker antes de continuar." >&2
  echo "Ex.: apt update && apt install -y docker.io docker-compose-v2" >&2
  exit 2
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 não encontrado." >&2
  exit 2
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl enable --now docker >/dev/null 2>&1 || true
fi

if [[ ! -f .env ]]; then
  cp .env.vps.example .env
  echo "Arquivo .env criado a partir de .env.vps.example."
  echo "Edite PUBLIC_IP, senhas e credenciais SSW e rode este script novamente."
  exit 3
fi

if grep -Eq '^(PUBLIC_IP=203\.0\.113\.10|DJANGO_SECRET_KEY=troque-|DJANGO_ADMIN_PASSWORD=troque-|POSTGRES_PASSWORD=troque-)' .env; then
  echo "ERRO: .env ainda contém valores de exemplo. Ajuste antes de publicar." >&2
  exit 4
fi

echo "==> Construindo e iniciando Painel Motoristas"
docker compose up -d --build --remove-orphans

echo "==> Estado dos serviços"
docker compose ps

IP=$(grep '^PUBLIC_IP=' .env | tail -1 | cut -d= -f2- | tr -d '\r')
echo
echo "Painel: http://${IP:-SEU_IP}/"
echo "Health: http://${IP:-SEU_IP}/healthz/"
echo "Os containers usam restart=unless-stopped e voltarão automaticamente após reboot da VPS."
