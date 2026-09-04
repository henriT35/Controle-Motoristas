#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker não encontrado." >&2
  echo "No Ubuntu da Hostinger, instale Docker + plugin Compose e rode novamente." >&2
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
  chmod 600 .env || true
  echo "Arquivo .env criado a partir de .env.vps.example."
  echo "Edite PUBLIC_IP, senhas e credenciais SSW e rode este script novamente."
  exit 3
fi

bash deploy/vps/preflight.sh

echo "==> Baixando/buildando imagens"
docker compose build --pull

echo "==> Subindo PostgreSQL e Redis"
docker compose up -d db redis

echo "==> Django check"
docker compose run --rm web python manage.py check

echo "==> Validando migrations versionadas"
docker compose run --rm web python manage.py makemigrations --check --dry-run

echo "==> Plano de migrations"
docker compose run --rm web python manage.py migrate --plan

echo "==> Subindo stack completa"
docker compose up -d --remove-orphans

echo "==> Aguardando health do Painel"
for i in $(seq 1 40); do
  if docker compose exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3).read()" >/dev/null 2>&1; then
    break
  fi
  sleep 3
  if [[ "$i" == "40" ]]; then
    echo "ERRO: web não ficou saudável a tempo." >&2
    docker compose logs --tail=120 web
    exit 5
  fi
done

bash deploy/vps/status.sh
IP=$(grep '^PUBLIC_IP=' .env | tail -1 | cut -d= -f2- | tr -d '\r')
echo
echo "Painel: http://${IP:-SEU_IP}/"
echo "Health: http://${IP:-SEU_IP}/healthz/"
echo "Containers usam restart=unless-stopped e voltarão após reboot da VPS."
