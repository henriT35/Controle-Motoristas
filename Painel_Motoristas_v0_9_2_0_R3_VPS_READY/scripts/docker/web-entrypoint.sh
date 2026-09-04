#!/usr/bin/env bash
set -euo pipefail
cd /app

echo "==> Validando projeto Django"
python manage.py check

echo "==> Validando migrations versionadas"
python manage.py makemigrations --check --dry-run

echo "==> Aplicando migrations"
python manage.py migrate --fake-initial --noinput

if [[ "${STARTUP_RECONCILE:-1}" == "1" ]]; then
  echo "==> Reconciliando comprovantes retidos"
  python manage.py reconcile_retained_proofs --apply --quiet
else
  echo "==> Reconciliação de retidos desativada no startup"
fi

if [[ "${STARTUP_SYNC_EVALUATION:-1}" == "1" ]]; then
  echo "==> Sincronizando avaliação V3"
  python manage.py sync_driver_evaluation_events --quiet --skip-warmup
else
  echo "==> Sincronização da avaliação desativada no startup"
fi

echo "==> Coletando arquivos estáticos"
python manage.py collectstatic --noinput

echo "==> Garantindo usuário administrador"
python scripts/docker/bootstrap_admin.py

if [[ "${STARTUP_WARMUP:-1}" == "1" ]]; then
  echo "==> Pré-aquecendo Dashboard/Ranking/Operação no Redis"
  if ! python manage.py warm_navigation_cache --quiet; then
    echo "AVISO: warmup falhou. O Painel será iniciado, mas o primeiro acesso pode ser mais lento." >&2
  fi
fi

echo "==> Iniciando Gunicorn"
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --max-requests "${GUNICORN_MAX_REQUESTS:-1000}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-100}" \
  --access-logfile - \
  --error-logfile -
