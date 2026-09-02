# Painel Motoristas v0.3.0.4 — Resiliência e Diagnóstico do Robô SSW

## Objetivo

Eliminar o cenário em que lentidão, indisponibilidade do SSW, travamento do navegador ou perda do processo deixa o Painel aguardando indefinidamente. A correção fica **fora do core Playwright homologado**.

## Arquitetura final

```text
Painel / fila
  -> dispatch.py
       -> preflight rápido (sem abrir Chromium)
       -> run_ssw_robot_guarded <run_id>
            -> processo-filho: run_ssw_robot <run_id>
                 -> robot_service.py
                 -> robot_ssw.run_job() [CORE HOMOLOGADO]
                 -> download
                 -> Import Engine
            -> heartbeat
            -> watchdog
            -> diagnóstico
            -> kill da árvore worker/browser se necessário
```

`DOWNLOADED` continua sendo apenas a fronteira Robô → Painel. `SUCCESS/WARNING` continua dependendo do Import Engine.

## Timeout e heartbeat

A configuração oficial usa:

```text
SSW_ROBOT_TIMEOUT_SECONDS=900
SSW_ROBOT_HEARTBEAT_SECONDS=10
SSW_ROBOT_ORPHAN_GRACE_SECONDS=120
```

Também é aceito `SSW_ROBOT_HARD_TIMEOUT_SECONDS` como override opcional do watchdog.

Ao atingir o timeout externo:

1. registra `WATCHDOG_TIMEOUT`;
2. encerra a árvore do processo-filho e do navegador (`taskkill /T /F` no Windows);
3. marca somente o `ImportRun` atual como `ERROR`;
4. grava `ROBOT_HARD_TIMEOUT`;
5. pausa a fila para impedir falhas em cascata;
6. preserva todas as janelas já concluídas e as janelas ainda `QUEUED`.

## Preservação do erro real

Mesmo quando `run_ssw_robot` encerra com código diferente de zero, o watchdog consulta `result.json`, `status.json` e `ImportRun.message` antes de classificar a falha. Assim, códigos como `DOWNLOAD_TIMEOUT`, `AUTH_OR_OPTION_TIMEOUT` e `SELECTOR_TIMEOUT` não são escondidos por um genérico `WORKER_EXIT_NONZERO`.

## Pausa da fila

O estado fica em:

```text
local_data/ssw_queue_paused.json
```

Enquanto a fila estiver pausada:

- `dispatch_next_robot_run()` não inicia outra janela;
- jobs já criados ficam `QUEUED`;
- scheduler automático não cria novas execuções de rotina;
- a tela `/ssw/importacoes/` e o histórico mostram o motivo da pausa.

Retomada:

```bash
python manage.py ssw_queue_control status
python manage.py ssw_queue_control resume
```

ou pelo botão **Retomar fila** no Painel.

## Retry somente da janela que falhou

No Histórico, uma execução `ERROR` tem o botão:

**Reprocessar somente esta janela**

Ele cria um novo `ImportRun` apenas para o período que falhou, retoma a fila e dá prioridade a esse retry. As demais janelas já concluídas não são recriadas e as pendentes continuam preservadas.

## Jobs órfãos / zumbis

O watchdog grava `worker_state.json` com PID, etapa e último heartbeat. Antes de iniciar um próximo job, o dispatch reconcilia execuções `DISPATCHED/RUNNING` sem processo vivo/heartbeat válido.

Código:

```text
ORPHAN_RUNNING_JOB
```

A execução órfã vira `ERROR` e a fila é pausada para inspeção.

Comando manual:

```bash
python manage.py ssw_reconcile_orphans
```

## Artefatos de diagnóstico

Por `execution_id`, em `imports/inbox/<execution_id>/`:

- `task.json`
- `events.jsonl`
- `orchestrator.log`
- `worker_process.log`
- `worker_state.json`
- `robot.log`
- `status.json`
- `result.json`
- `diagnostic.json`
- `environment.json`
- `evidence_*.png` quando o core gerar evidência

O pacote técnico **não inclui o relatório SSW** nem `.env`.

Gerar via CLI:

```bash
python manage.py ssw_diagnostic_pack SSW-20260901-103000-000123
```

Ou usar **Baixar diagnóstico técnico** no Histórico.

## Segurança

A sanitização mascara `password`, `senha`, `token`, `cookie`, `authorization` e `secret`. O core continua responsável por sanitizar as próprias credenciais; a camada nova não grava `.env` no pacote diagnóstico.

## Core homologado

A v0.3.0.4 não altera nenhum arquivo de `robot_ssw/`. O contrato homologado permanece:

```text
login ►
-> preencher 036
-> Enter
-> expect_popup
-> Excel=S
-> Unidade=BEL
-> DDMMYY
-> #btn_env_periodo.click()
-> expect_download
-> DOWNLOADED
```
