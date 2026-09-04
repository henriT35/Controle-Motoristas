#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p backups
chmod 700 backups || true
STAMP=$(date +%Y%m%d_%H%M%S)
DIR="backups/${STAMP}"
mkdir -p "$DIR"
chmod 700 "$DIR" || true

env_value() {
  local key=$1 default=${2:-}
  local value=""
  if [[ -f .env ]]; then
    value=$(grep -E "^${key}=" .env | tail -1 | cut -d= -f2- | tr -d '\r' || true)
    value=${value%\"}; value=${value#\"}
    value=${value%\'}; value=${value#\'}
  fi
  printf '%s' "${value:-$default}"
}
DB=$(env_value POSTGRES_DB painel_motoristas)
USER=$(env_value POSTGRES_USER painel)

echo "==> Backup PostgreSQL"
docker compose exec -T db pg_dump -U "$USER" -Fc "$DB" > "$DIR/postgres.dump"

echo "==> Backup local_data/media/imports"
docker compose exec -T web tar -czf - -C /app local_data media imports > "$DIR/app_persistent.tar.gz"

cat > "$DIR/README.txt" <<TXT
Backup Painel Motoristas: ${STAMP}
- postgres.dump: pg_dump formato custom
- app_persistent.tar.gz: local_data, media e imports
ATENÇÃO: local_data pode conter sessão Baileys/tokens. Trate este diretório como segredo.
TXT

sha256sum "$DIR/postgres.dump" "$DIR/app_persistent.tar.gz" > "$DIR/SHA256SUMS.txt"
echo "Backup criado: $DIR"
