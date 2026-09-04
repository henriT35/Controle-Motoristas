#!/usr/bin/env bash
set -euo pipefail
cd /app

required=(SSW_EMPRESA SSW_CPF SSW_USUARIO SSW_SENHA)
missing=()
for key in "${required[@]}"; do
  [[ -n "${!key:-}" ]] || missing+=("$key")
done
if (( ${#missing[@]} )); then
  echo "ERRO: credenciais SSW ausentes: ${missing[*]}" >&2
  exit 2
fi

cat > /app/robot_ssw/.env <<EOF
SSW_URL=${SSW_URL:-https://sistema.ssw.inf.br/bin/ssw0422}
SSW_EMPRESA=${SSW_EMPRESA}
SSW_CPF=${SSW_CPF}
SSW_USUARIO=${SSW_USUARIO}
SSW_SENHA=${SSW_SENHA}
SSW_UNIT=${SSW_UNIT:-BEL}
SSW_REPORT_TYPE=${SSW_REPORT_TYPE:-ROMANEIOS}
SSW_OPTION=${SSW_OPTION:-036}
ROBOT_HEADLESS=${ROBOT_HEADLESS:-true}
ROBOT_SLOW_MO=${ROBOT_SLOW_MO:-800}
ROBOT_ACTION_TIMEOUT_MS=${ROBOT_ACTION_TIMEOUT_MS:-30000}
ROBOT_DOWNLOAD_TIMEOUT_MS=${ROBOT_DOWNLOAD_TIMEOUT_MS:-120000}
ROBOT_MAX_DAYS=${ROBOT_MAX_DAYS:-31}
ROBOT_INBOX_DIR=/app/imports/inbox
EOF
chmod 600 /app/robot_ssw/.env
mkdir -p /app/imports/inbox /app/local_data/logs
exec "$@"
