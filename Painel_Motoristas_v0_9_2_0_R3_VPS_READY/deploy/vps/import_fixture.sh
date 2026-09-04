#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
FIXTURE=${1:-}
if [[ -z "$FIXTURE" || ! -f "$FIXTURE" ]]; then
  echo "Uso: bash deploy/vps/import_fixture.sh /caminho/painel_data.json" >&2
  exit 2
fi

echo "ATENÇÃO: importe apenas fixture gerada pela MESMA versão do projeto."
echo "==> Backup antes da importação"
bash deploy/vps/backup.sh

docker compose cp "$FIXTURE" web:/tmp/painel_data.json
docker compose exec -T web python manage.py loaddata /tmp/painel_data.json
docker compose exec -T web rm -f /tmp/painel_data.json

echo "==> Sincronizando avaliação/retenções e aquecendo cache"
docker compose exec -T web python manage.py reconcile_retained_proofs --apply --quiet
docker compose exec -T web python manage.py sync_driver_evaluation_events --quiet
docker compose exec -T web python manage.py warm_navigation_cache --quiet

echo "Importação concluída."
