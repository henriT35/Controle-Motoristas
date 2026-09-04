#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

fail=0
warn() { echo "AVISO: $*"; }
err() { echo "ERRO: $*" >&2; fail=1; }

command -v docker >/dev/null 2>&1 || err "Docker não encontrado."
docker compose version >/dev/null 2>&1 || err "Docker Compose v2 não encontrado."

[[ -f .env ]] || err "Arquivo .env não encontrado. Copie .env.vps.example para .env."

if [[ -f .env ]]; then
  if grep -Eq '^(PUBLIC_IP=203\.0\.113\.10|DJANGO_SECRET_KEY=troque-|DJANGO_ADMIN_PASSWORD=troque-|POSTGRES_PASSWORD=troque-)' .env; then
    err ".env ainda contém valores de exemplo."
  fi
  if ! grep -Eq '^PUBLIC_IP=([0-9]{1,3}\.){3}[0-9]{1,3}$' .env; then
    warn "PUBLIC_IP não parece um IPv4. Confirme antes de publicar."
  fi
  if grep -Eq '^(SSW_EMPRESA|SSW_CPF|SSW_USUARIO|SSW_SENHA)=$' .env; then
    warn "Há credenciais SSW vazias. robot-worker não ficará saudável até preenchê-las."
  fi
fi

avail_mb=$(df -Pm . | awk 'NR==2 {print $4}')
if [[ -n "${avail_mb:-}" && "$avail_mb" -lt 8192 ]]; then
  warn "Menos de 8 GB livres em disco (${avail_mb} MB). Docker + Playwright + backups podem consumir espaço rapidamente."
fi

mem_mb=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || true)
if [[ -n "${mem_mb:-}" && "$mem_mb" -lt 3000 ]]; then
  warn "VPS com menos de ~3 GB RAM detectada (${mem_mb} MB). Use GUNICORN_WORKERS=2 e CELERY_WORKER_CONCURRENCY=1, e configure swap."
fi

if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:)80$'; then
  warn "Porta 80 já está em uso. Verifique Apache/Nginx antigo antes de subir o compose."
fi

if docker compose config -q >/dev/null 2>&1; then
  echo "Compose config: OK"
else
  err "docker compose config falhou. Revise docker-compose.yml e .env."
fi

if [[ "$fail" -ne 0 ]]; then
  exit 2
fi

echo "Preflight VPS: OK"
