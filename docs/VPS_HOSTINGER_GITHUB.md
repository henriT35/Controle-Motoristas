# Deploy Hostinger VPS via GitHub — v0.8.0.0

## Arquitetura

A VPS executa o produto inteiro por Docker Compose:

- `nginx`: porta pública 80, sem domínio;
- `web`: Django + Gunicorn;
- `db`: PostgreSQL;
- `redis`: broker/fila;
- `worker`: tarefas gerais Celery;
- `beat`: scheduler automático;
- `robot-worker`: core homologado SSW 036 em Playwright/Chromium Linux;
- `whatsapp`: Node.js + Baileys.

O `robot_ssw` permanece com o mesmo core. A adaptação para Linux acontece no container e nas variáveis de execução, não na lógica homologada.

## 1. Subir para GitHub

Na máquina de desenvolvimento:

```bash
git init
git add .
git commit -m "Painel Motoristas v0.8.0.0"
git branch -M main
git remote add origin SEU_REPOSITORIO_GITHUB
git push -u origin main
```

Nunca versionar `.env`, `local_data`, sessão Baileys, banco, credenciais SSW, uploads ou `node_modules`.

## 2. Clonar na Hostinger

```bash
git clone SEU_REPOSITORIO_GITHUB painel-motoristas
cd painel-motoristas
cp .env.vps.example .env
nano .env
```

Preencha no mínimo:

- `PUBLIC_IP`;
- `DJANGO_SECRET_KEY`;
- `DJANGO_ADMIN_PASSWORD`;
- `POSTGRES_PASSWORD`;
- `SSW_EMPRESA`, `SSW_CPF`, `SSW_USUARIO`, `SSW_SENHA`.

## 3. Primeira subida

```bash
chmod +x deploy/vps/*.sh scripts/docker/*.sh
./deploy/vps/install.sh
```

Acesso inicial:

```text
http://IP_PUBLICO_DA_VPS/
```

Sem domínio e sem TLS nesta primeira arquitetura. O modo de IP direto configura cookies para HTTP. Como o Portal usa tokens, HTTPS continua recomendado para uma etapa posterior, mesmo sem domínio próprio.

## 4. Atualizar pelo GitHub

```bash
cd painel-motoristas
./deploy/vps/update.sh
```

O script executa `git pull --ff-only` e `docker compose up -d --build`. Volumes de PostgreSQL, Redis, `local_data`, uploads e sessão WhatsApp não são apagados.

## 5. Boot automático

Todos os serviços usam `restart: unless-stopped`. O instalador também tenta habilitar o serviço Docker no boot do Ubuntu. Após reboot da VPS, Django, scheduler, robô SSW e Baileys sobem novamente sem comando manual.

## 6. Automação SSW

O Celery Beat acorda a cada minuto. O intervalo real fica em `local_data/ssw_schedule.json` e é alterado pela tela **SSW → Importações e Sincronização**.

Opções iniciais: 30 min, 1h, 2h, 3h e 6h. O botão **Atualizar agora** cria uma execução FAST imediatamente usando o mesmo lock da fila; se o robô já estiver executando, a nova solicitação permanece enfileirada/deduplicada.

## 7. Teste obrigatório do robô na VPS

Antes de considerar o deploy homologado, confirmar no Linux:

1. Chromium do container inicia;
2. SSW abre pela rede da VPS;
3. autenticação funciona;
4. opção 036 funciona;
5. download `.sswweb` chega em `/app/imports/inbox`;
6. importação atualiza PostgreSQL;
7. watchdog encerra corretamente uma falha.

Se o SSW bloquear IP de datacenter ou exigir comportamento específico do Windows, isso deve ser tratado como resultado de homologação; não alterar o core às cegas.

## 8. WhatsApp

O container `whatsapp` compartilha apenas o volume `local_data` com Django. A sessão fica em `local_data/whatsapp/baileys_auth` e sobrevive a rebuilds/`git pull`.

O Nginx bloqueia `/whatsapp/internal/` externamente. A comunicação Node → Django usa rede Docker interna + token aleatório compartilhado.

## 9. Diagnóstico

```bash
./deploy/vps/status.sh
docker compose logs -f robot-worker
docker compose logs -f whatsapp
docker compose logs -f beat
```
