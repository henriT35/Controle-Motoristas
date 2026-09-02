# Arquivos alterados — v0.3.0.4

## Integração / execução
- `apps/ssw/dispatch.py`
- `apps/ssw/tasks.py`
- `config/settings.py`
- `.env.example`
- `.env.local.example`

## Novos módulos de resiliência
- `apps/ssw/diagnostics.py`
- `apps/ssw/management/commands/run_ssw_robot_guarded.py`
- `apps/ssw/management/commands/ssw_queue_control.py`
- `apps/ssw/management/commands/ssw_diagnostic_pack.py`
- `apps/ssw/management/commands/ssw_reconcile_orphans.py`

## Interface
- `apps/ssw/views.py`
- `apps/ssw/urls.py`
- `templates/ssw/imports.html`
- `templates/ssw/history.html`

## QA / operação
- `scripts/qa_resilience_v0304.py`
- `TESTAR_RESILIENCIA_SSW_V0_3_0_4.bat`
- `RETOMAR_FILA_SSW_V0_3_0_4.bat`

## Documentação / release
- `VERSION.txt`
- `README.md`
- `RELEASE_MANIFEST.txt`
- `docs/CHANGELOG.md`
- `docs/RESILIENCIA_ROBO_SSW_V0_3_0_4.md`
- `docs/ESPECIFICACAO_LOG_DIAGNOSTICO_SSW_v0.3.0.4.md`
- `docs/QA_V0_3_0_4.md`

## Congelado / não alterado
Todo o diretório `robot_ssw/` foi preservado byte a byte em relação à baseline v0.3.0.3.
