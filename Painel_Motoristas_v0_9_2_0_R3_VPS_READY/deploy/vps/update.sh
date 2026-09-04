#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

bash deploy/vps/preflight.sh

echo "==> Backup antes da atualização"
bash deploy/vps/backup.sh

echo "==> Atualizando código"
git pull --ff-only

echo "==> Build das novas imagens"
docker compose build --pull

echo "==> Garantindo banco/Redis"
docker compose up -d db redis

echo "==> Validando Django e migrations antes de trocar web"
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py migrate --plan

echo "==> Aplicando stack"
docker compose up -d --remove-orphans

echo "==> Status final"
bash deploy/vps/status.sh
