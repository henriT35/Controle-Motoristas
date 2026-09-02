#!/usr/bin/env bash
set -euo pipefail
cd /app

echo "==> Aplicando banco (migrate --run-syncdb)"
python manage.py migrate --run-syncdb --noinput

echo "==> Coletando arquivos estáticos"
python manage.py collectstatic --noinput

echo "==> Garantindo usuário administrador"
python scripts/docker/bootstrap_admin.py

echo "==> Iniciando Gunicorn"
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" --threads "${GUNICORN_THREADS:-2}" --timeout "${GUNICORN_TIMEOUT:-120}" --access-logfile - --error-logfile -
