#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "==> Atualizando código do GitHub"
git pull --ff-only

echo "==> Rebuild sem derrubar volumes persistentes"
docker compose up -d --build --remove-orphans

echo "==> Serviços"
docker compose ps
