#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
env_value() {
  local key=$1 default=${2:-}
  local value=""
  if [[ -f .env ]]; then value=$(grep -E "^${key}=" .env | tail -1 | cut -d= -f2- | tr -d '\r' || true); fi
  value=${value%\"}; value=${value#\"}; value=${value%\'}; value=${value#\'}
  printf '%s' "${value:-$default}"
}
DB=$(env_value POSTGRES_DB painel_motoristas)
USER=$(env_value POSTGRES_USER painel)

docker compose ps
echo
echo "--- health Django ---"
if docker compose exec -T web python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=5).read().decode())" 2>/dev/null; then :; else echo "health Django: FALHOU"; fi

echo
echo "--- PostgreSQL ---"
docker compose exec -T db pg_isready -U "$USER" -d "$DB" || true

echo
echo "--- Redis ---"
docker compose exec -T redis redis-cli ping || true

echo
echo "--- últimos logs web ---"
docker compose logs --tail=35 web

echo
echo "--- últimos logs robot-worker ---"
docker compose logs --tail=25 robot-worker

echo
echo "--- últimos logs whatsapp ---"
docker compose logs --tail=25 whatsapp
