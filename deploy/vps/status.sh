#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose ps
echo
echo "--- últimos logs web ---"
docker compose logs --tail=40 web
echo
echo "--- últimos logs robot-worker ---"
docker compose logs --tail=40 robot-worker
echo
echo "--- últimos logs whatsapp ---"
docker compose logs --tail=40 whatsapp
