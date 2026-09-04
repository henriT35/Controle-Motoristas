# QA — Painel Motoristas v0.9.2.0 R3 VPS Ready

## Escopo

Preparação da baseline R3 otimizada para VPS sem domínio, mantendo a arquitetura oficial:

- Nginx;
- Django/Gunicorn;
- PostgreSQL;
- Redis;
- Celery worker;
- Celery Beat;
- robot-worker SSW/Playwright;
- WhatsApp Node.js/Baileys.

## Alterações de infraestrutura verificadas

- `web` incluído em `DJANGO_ALLOWED_HOSTS` para a chamada interna do Baileys;
- `DJANGO_CSRF_TRUSTED_ORIGINS` configurado para o IP HTTP;
- Redis DB 0 reservado ao Celery e DB 1 ao cache Django;
- warmup R3 antes do Gunicorn;
- sincronização V3 no startup sem warmup duplicado (`--skip-warmup`);
- Gunicorn configurável pelo `.env` e com `max-requests`/jitter;
- Celery worker configurável e com `max-tasks-per-child`;
- healthcheck do WhatsApp por heartbeat;
- healthcheck do Nginx;
- scripts de preflight, healthcheck, logs, backup e update;
- backup inclui PostgreSQL + `local_data` + `media` + `imports`;
- exportação Windows/SQLite para fixture Django destinada ao PostgreSQL da VPS;
- documentação corrigida para usar `.env` como arquivo ativo do Docker Compose.

## QA realmente executado

### PASS

- `python -m compileall` em toda a árvore;
- `node --check whatsapp_bridge/server.mjs`;
- `node --check whatsapp_bridge/healthcheck.mjs`;
- `bash -n` em scripts Docker/VPS;
- parse estrutural de `docker-compose.yml` com PyYAML;
- presença dos 8 serviços obrigatórios no Compose;
- porta Nginx 80:80;
- Redis cache separado em DB 1;
- `web` presente no `ALLOWED_HOSTS` do container;
- healthcheck WhatsApp referenciando `healthcheck.mjs`;
- `scripts/qa/portable_qa.py` — 6/6 PASS;
- `test_navigation_performance_v092_r3_static.py` — PASS;
- `test_vps_ready_static.py` — PASS;
- migrations v0.9.1/v0.9.2 static QA — PASS;
- performance/formula/snapshot/EXACT history — PASS;
- rotas/templates — PASS;
- temporalidade v0.9.1 — PASS;
- contratos v0.9.1/v0.9.2 — PASS;
- WhatsApp Baileys static QA — PASS;
- telefone BR — PASS;
- `robot_ssw`: 17/17 arquivos byte a byte/SHA-256 idênticos à baseline R3 de origem.

## Homologação externa pendente

O ambiente de empacotamento não possui Docker nem Django instalados. Portanto NÃO foram inventados resultados para:

- `docker compose config` real;
- build real das imagens;
- `docker compose up`;
- `manage.py check` dentro do container;
- `makemigrations --check` dentro do container;
- migrations PostgreSQL reais;
- health real PostgreSQL/Redis;
- Gunicorn/Nginx HTTP real;
- Celery/Beat reais;
- robot-worker/Chromium/SSW real;
- Baileys/QR real;
- reboot real da VPS;
- benchmark de performance na VPS.

Esses testes são executados pelo fluxo `deploy/vps/install.sh`/`healthcheck.sh` no host real.

## Regra de promoção

Antes de considerar VPS homologada:

```bash
bash deploy/vps/preflight.sh
bash deploy/vps/install.sh
bash deploy/vps/healthcheck.sh
```

Depois homologar Dashboard, Operação, Ranking, Retidos, Avaliações, Portal, WhatsApp e SSW 036 no ambiente real.
