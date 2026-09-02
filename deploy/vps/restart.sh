#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose restart web worker beat robot-worker whatsapp nginx
docker compose ps
