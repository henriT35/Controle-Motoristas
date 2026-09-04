# ARQUITETURA ATUAL E ALVO VPS

## Execução local Windows
- Django local/Waitress;
- SQLite por padrão;
- scheduler SSW como processo `run_ssw_scheduler`;
- Baileys como processo Node separado;
- Quick Tunnel opcional para exposição temporária.

## Execução VPS
```text
Internet
  ↓
Nginx :80
  ↓
Django / Gunicorn
  ├── PostgreSQL
  ├── Redis
  ├── Celery worker
  ├── Celery Beat
  ├── robot-worker SSW (Playwright/Chromium)
  └── WhatsApp bridge Node/Baileys
```

## Containers v0.8.2.0
- `db`
- `redis`
- `web`
- `worker`
- `beat`
- `robot-worker`
- `whatsapp`
- `nginx`

Todos devem usar restart automático na VPS.

## Persistência
- PostgreSQL: `postgres_data`;
- Redis: `redis_data`;
- estado local/sessão WhatsApp: `local_data`;
- uploads: `media_data`;
- imports: `imports_data`.

## Sem domínio
A arquitetura foi preparada para `http://IP_PUBLICO_DA_VPS`. O Portal usa tokens; HTTPS continua recomendado como endurecimento futuro.
