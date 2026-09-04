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

fail=0
ok() { echo "OK   $*"; }
bad() { echo "FALHA $*"; fail=1; }

if docker compose exec -T db pg_isready -U "$USER" -d "$DB" >/dev/null 2>&1; then ok PostgreSQL; else bad PostgreSQL; fi
if [[ "$(docker compose exec -T redis redis-cli ping 2>/dev/null | tr -d '\r')" == "PONG" ]]; then ok Redis; else bad Redis; fi
if docker compose exec -T web python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=5).read()" >/dev/null 2>&1; then ok Django; else bad Django; fi

running=$(docker compose ps --status running --services 2>/dev/null || true)
for svc in web worker beat robot-worker whatsapp nginx; do
  if grep -qx "$svc" <<<"$running"; then ok "$svc running"; else bad "$svc não está running"; fi
done

if [[ "$fail" -ne 0 ]]; then
  echo
  echo "Use: docker compose logs --tail=150 <serviço>"
  exit 2
fi
