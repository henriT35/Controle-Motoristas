# Patch v0.8.0.1

Hotfix de inicialização da Central SSW no Windows/local e VPS.

## Sintoma corrigido

`NameError: name 'require_POST' is not defined` ao executar `manage.py makemigrations`, `check`, `migrate` ou iniciar o servidor.

## Causa

Os endpoints `update_schedule` e `trigger_fast_sync` usam `@require_POST`, mas a importação do decorator não estava presente em `apps/ssw/views.py`.

## Escopo

- adiciona a importação ausente;
- adiciona QA estático para decorators do módulo SSW;
- não altera models nem migrations;
- não altera `robot_ssw`;
- não altera sessão/bridge Baileys.
