#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose restart web worker beat robot-worker whatsapp nginx
sleep 3
bash deploy/vps/status.sh
