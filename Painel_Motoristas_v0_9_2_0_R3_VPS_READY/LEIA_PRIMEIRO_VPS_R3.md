# PAINEL MOTORISTAS v0.9.2.0 R3 — VPS READY

Esta árvore foi preparada para a arquitetura de VPS já definida no projeto:

`nginx + web/Gunicorn + PostgreSQL + Redis + Celery worker + Beat + robot-worker SSW + WhatsApp/Baileys`.

## Deploy rápido

```bash
cp .env.vps.example .env
nano .env
bash deploy/vps/preflight.sh
bash deploy/vps/install.sh
```

Acesso inicial, sem domínio:

`http://SEU_IP_PUBLICO/`

## Melhorias específicas desta preparação

- `ALLOWED_HOSTS` inclui o hostname Docker `web` para comunicação interna do Baileys;
- Celery usa Redis DB 0 e cache Django usa DB 1;
- warmup R3 roda antes de abrir Gunicorn por padrão;
- parâmetros Gunicorn/Celery configuráveis pelo `.env`;
- healthchecks adicionais para WhatsApp e Nginx;
- Nginx com gzip/proxy buffers;
- preflight VPS;
- backup de PostgreSQL + local_data/media/imports;
- healthcheck consolidado;
- fluxo seguro de update com backup;
- exportação de dados SQLite/Windows para importação no PostgreSQL da VPS;
- documentação corrigida para usar `.env`, que é o arquivo lido pelo Compose.

## Dados

Se quiser levar os dados do computador atual para a VPS, execute no Windows:

`EXPORTAR_DADOS_PARA_VPS.bat`

Leia `docs/VPS_HOSTINGER_GITHUB.md` antes do deploy definitivo.

## Regra crítica

`robot_ssw/` não foi alterado por esta preparação.
