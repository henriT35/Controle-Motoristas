# Hotfix v0.3.0.7 — Retry isolado SSW

## Erro corrigido

Ao clicar em **Reprocessar** no Histórico SSW, a view `retry_failed_run()` chama:

`dispatch_robot_run(new_run.pk, priority=True)`

O patch cumulativo v0.3.0.6 havia reintroduzido por engano uma versão antiga de `dispatch.py` cuja função aceitava apenas `run_id`, causando:

`TypeError: dispatch_robot_run() got an unexpected keyword argument 'priority'`

## Correção

- restaura o contrato `dispatch_robot_run(run_id, *, priority=False)`;
- preserva o despacho protegido por `run_ssw_robot_guarded`;
- preserva pausa/retomada da fila;
- preserva o retry isolado da janela com erro;
- não altera `robot_ssw/`.

## QA

O instalador executa `scripts/qa_retry_dispatch_v0307.py` e só finaliza a versão se:

1. `priority` existir na assinatura;
2. a view continuar chamando `priority=True`;
3. o watchdog continuar ativo no dispatcher.
