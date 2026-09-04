#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
SERVICE=${1:-}
if [[ -n "$SERVICE" ]]; then
  exec docker compose logs -f --tail=150 "$SERVICE"
fi
exec docker compose logs -f --tail=80 web worker beat robot-worker whatsapp nginx
