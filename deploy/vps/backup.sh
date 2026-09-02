#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p backups
STAMP=$(date +%Y%m%d_%H%M%S)
DB=${POSTGRES_DB:-painel_motoristas}
USER=${POSTGRES_USER:-painel}
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  DB=${POSTGRES_DB:-painel_motoristas}
  USER=${POSTGRES_USER:-painel}
fi
docker compose exec -T db pg_dump -U "$USER" "$DB" | gzip > "backups/postgres_${STAMP}.sql.gz"
echo "Backup criado: backups/postgres_${STAMP}.sql.gz"
