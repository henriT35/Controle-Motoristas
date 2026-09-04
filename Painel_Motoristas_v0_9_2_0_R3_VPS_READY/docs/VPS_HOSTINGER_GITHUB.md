# GitHub → Hostinger VPS — v0.9.2.0 R3 VPS Ready

## Objetivo

Executar o Painel Motoristas 24h na VPS, inicialmente **sem domínio**, acessando pelo IP público:

`http://IP_PUBLICO_DA_VPS`

A stack de produção usa:

- Nginx na porta 80;
- Django + Gunicorn;
- PostgreSQL 17;
- Redis (broker Celery + cache compartilhado em DBs Redis separadas);
- Celery worker;
- Celery Beat;
- robot-worker dedicado para SSW 036/Playwright, concurrency=1;
- WhatsApp Node.js/Baileys com sessão persistente.

Todos os serviços usam `restart: unless-stopped`.

## 1. Requisitos sugeridos da VPS

Ponto de partida recomendado para stack completa:

- Ubuntu recente;
- Docker + Docker Compose v2;
- 4 GB RAM recomendado;
- 2 vCPU ou mais;
- 15–20 GB livres de disco;
- porta TCP 80 liberada;
- swap configurado se a VPS tiver pouca memória.

Abaixo de ~3 GB RAM, comece com:

```env
GUNICORN_WORKERS=2
CELERY_WORKER_CONCURRENCY=1
```

O Playwright/Chromium do robot-worker é o componente mais pesado em memória.

## 2. Primeiro deploy via GitHub

```bash
git clone https://github.com/henriT35/Controle-Motoristas.git
cd Controle-Motoristas
cp .env.vps.example .env
nano .env
chmod 600 .env
bash deploy/vps/preflight.sh
bash deploy/vps/install.sh
```

**Importante:** Docker Compose lê `.env`. Não use `.env.vps` como arquivo ativo sem passar `--env-file` explicitamente.

O `install.sh`:

1. valida ambiente e `.env`;
2. builda as imagens;
3. sobe PostgreSQL e Redis;
4. executa `manage.py check`;
5. executa `makemigrations --check --dry-run`;
6. mostra o plano de migrations;
7. sobe a stack completa;
8. espera o `/healthz/` responder.

## 3. Arquivo `.env`

Preencha obrigatoriamente:

- `PUBLIC_IP`;
- `DJANGO_SECRET_KEY`;
- senha de admin;
- senha do PostgreSQL;
- credenciais SSW.

A stack adiciona `web` ao `ALLOWED_HOSTS`, pois o Baileys chama o Django internamente por `http://web:8000`.

Redis:

- DB 0: Celery;
- DB 1: cache Django.

Isso evita misturar chaves de cache com o broker.

## 4. Performance R3 na VPS

No startup, por padrão:

```env
STARTUP_RECONCILE=1
STARTUP_SYNC_EVALUATION=1
STARTUP_WARMUP=1
```

Antes de liberar o Gunicorn, o container web:

- aplica migrations;
- reconcilia comprovantes;
- sincroniza avaliação V3;
- pré-aquece Ranking, Dashboard, gráfico e oportunidades no Redis.

A intenção é evitar que o primeiro usuário da VPS pague o custo do ranking/cache frio.

Depois das importações SSW e housekeeping, o próprio código também atualiza snapshots/cache.

## 5. Verificação

```bash
bash deploy/vps/healthcheck.sh
```

Ou:

```bash
bash deploy/vps/status.sh
```

Logs:

```bash
bash deploy/vps/logs.sh
bash deploy/vps/logs.sh web
bash deploy/vps/logs.sh robot-worker
bash deploy/vps/logs.sh whatsapp
```

URLs:

```text
http://IP_PUBLICO/
http://IP_PUBLICO/healthz/
```

## 6. WhatsApp/Baileys

A sessão fica no volume persistente compartilhado em:

`local_data/whatsapp/baileys_auth/`

O container `whatsapp` tem healthcheck baseado no heartbeat do `state.json`.

A API interna `/whatsapp/internal/` é bloqueada no Nginx e não deve ser exposta à internet.

No primeiro deploy, faça um novo pareamento pelo QR Code no Painel. Por segurança, o exportador local não copia automaticamente a sessão Baileys para a VPS.

## 7. Robô SSW

O `robot_ssw/` continua congelado. O container `robot-worker` usa Playwright e somente fila `ssw`, com concurrency=1.

Credenciais vêm do `.env` da VPS e são materializadas dentro do container em `/app/robot_ssw/.env` com permissão 600. Nunca versionar credenciais.

## 8. Migrar dados do Windows/SQLite para PostgreSQL da VPS

Na cópia local da mesma versão, execute:

`EXPORTAR_DADOS_PARA_VPS.bat`

Ele cria em `local_data/vps_transfer_*`:

- `painel_data.json`;
- `media.tar.gz` se houver mídia;
- hashes SHA-256;
- instruções.

Essa pasta é **sensível** e nunca deve ir para o GitHub.

Copie `painel_data.json` para a VPS via SCP/SFTP e rode:

```bash
bash deploy/vps/import_fixture.sh /caminho/painel_data.json
```

Para a mídia:

```bash
docker compose cp media.tar.gz web:/tmp/media.tar.gz
docker compose exec -T web sh -lc 'cd /app && tar -xzf /tmp/media.tar.gz && rm /tmp/media.tar.gz'
```

Depois:

```bash
docker compose exec -T web python manage.py warm_navigation_cache --quiet
```

## 9. Backup

```bash
bash deploy/vps/backup.sh
```

O backup inclui:

- `postgres.dump` em formato custom do pg_dump;
- `app_persistent.tar.gz` com `local_data`, `media` e `imports`;
- hashes SHA-256.

**Atenção:** `local_data` contém sessão/token do WhatsApp. O backup deve ser protegido como segredo.

## 10. Atualização pelo GitHub

```bash
bash deploy/vps/update.sh
```

O script faz backup antes do `git pull`, valida Django/migrations e rebuilda a stack sem remover volumes persistentes.

Não use:

```bash
docker compose down -v
```

em produção, pois `-v` remove volumes persistentes.

## 11. Reboot da VPS

Teste uma vez após homologação:

```bash
sudo reboot
```

Depois:

```bash
cd Controle-Motoristas
bash deploy/vps/healthcheck.sh
```

Esperado: db, redis, web, worker, beat, robot-worker, whatsapp e nginx voltam automaticamente.

## 12. Sem domínio / segurança

Neste estágio o sistema usa HTTP por IP. Por isso cookies seguros e redirect HTTPS estão desligados no compose.

Isso é funcional para homologação, mas tokens do Portal trafegam sem criptografia. Quando houver domínio, migrar para HTTPS e ativar:

- `DJANGO_SECURE_COOKIES=1`;
- `DJANGO_SECURE_SSL_REDIRECT=1`;
- `PANEL_PUBLIC_BASE_URL=https://...`;
- `CSRF_TRUSTED_ORIGINS=https://...`.

## 13. Nunca versionar

- `.env` / `.env.local`;
- credenciais SSW;
- sessão Baileys;
- dumps PostgreSQL;
- `local_data`;
- media real;
- imports/relatórios reais;
- logs;
- `.venv`;
- `node_modules`.

## 14. Comandos úteis

```bash
# serviços
docker compose ps

# health
bash deploy/vps/healthcheck.sh

# logs
bash deploy/vps/logs.sh web

# reiniciar aplicação sem apagar dados
bash deploy/vps/restart.sh

# Django
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py migrate --plan

# warmup R3
docker compose exec -T web python manage.py warm_navigation_cache --quiet

# reconciliação segura primeiro em dry-run
docker compose exec -T web python manage.py reconcile_retained_proofs --dry-run
```
