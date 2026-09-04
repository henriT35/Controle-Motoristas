# Painel Motoristas — Especificação de Log de Diagnóstico SSW

**Versão proposta:** v0.3.0.4  
**Objetivo:** transformar os logs do Painel/Robô SSW em uma trilha de diagnóstico suficiente para localizar falhas de fila, bridge, worker, navegador, SSW, download e importação sem precisar reproduzir o problema às cegas.

---

## 1. Princípios

1. Toda execução possui um `execution_id` único.
2. Se existir uma fila/lote, toda execução também recebe um `batch_id`.
3. Todo evento relevante registra `timestamp`, componente, etapa, status, duração e contexto.
4. Logs não podem conter senha, cookie, token, CPF de login ou demais segredos.
5. O core homologado do Playwright não deve ser reescrito apenas para logging.
6. O logging detalhado deve ser acrescentado principalmente no orquestrador, bridge, callback, watchdog e importador.
7. O log nunca pode impedir ou derrubar a execução principal. Falha ao gravar telemetria deve ser tratada separadamente.
8. `DOWNLOADED` continua não significando `SUCCESS`.
9. Reprocessamento nunca apaga o log/histórico da tentativa anterior.
10. Logs devem permitir identificar jobs zumbis, perda de heartbeat, processos mortos, locks presos, timeouts e reprocessamentos.

---

## 2. Estrutura por execução

```text
local_data/
└── ssw_runs/
    └── <execution_id>/
        ├── events.jsonl
        ├── robot.log
        ├── status.json
        ├── result.json
        ├── diagnostic.json
        ├── traceback.txt
        ├── evidence_001.png
        └── relatorio_036.<extensão>
```

### Arquivos

- `events.jsonl`: fonte principal estruturada; um JSON por evento.
- `robot.log`: versão legível para humanos.
- `status.json`: fotografia do estado atual.
- `result.json`: resultado técnico final.
- `diagnostic.json`: resumo automático criado ao finalizar/falhar.
- `traceback.txt`: traceback sanitizado somente quando houver exceção.
- `evidence_*.png`: screenshot sanitizado em falhas onde for seguro.
- relatório: arquivo realmente baixado, quando houver.

---

## 3. Campos obrigatórios de todo evento

```json
{
  "timestamp": "2026-08-31T23:12:33.522-03:00",
  "level": "INFO",
  "event": "WAITING_DOWNLOAD_STARTED",
  "component": "robot_ssw",
  "execution_id": "SSW-20260831-00125",
  "batch_id": "BATCH-20260831-00004",
  "attempt": 1,
  "start_date": "2026-08-01",
  "end_date": "2026-08-31",
  "stage": "WAITING_DOWNLOAD",
  "status_before": "REQUESTING_REPORT",
  "status_after": "WAITING_DOWNLOAD",
  "elapsed_ms": 0,
  "message": "Solicitação enviada; aguardando download."
}
```

### Sempre registrar

- `timestamp`
- `level`
- `event`
- `component`
- `execution_id`
- `batch_id` quando aplicável
- `attempt`
- `start_date`
- `end_date`
- `stage`
- `status_before`
- `status_after`
- `elapsed_ms`
- `message`

---

## 4. Contexto técnico adicional

Adicionar quando aplicável:

```json
{
  "worker_pid": 13844,
  "browser_pid": 19420,
  "parent_pid": 10212,
  "hostname": "PC-ROBO-SSW",
  "thread_id": 5168,
  "python_version": "3.x",
  "app_version": "0.3.0.4",
  "robot_build": "core-homologado-<hash>",
  "import_engine_build": "v2-<hash>",
  "queue_position": 4,
  "lock_key": "ssw-queue.lock",
  "lock_acquired": true,
  "last_heartbeat_at": "2026-08-31T23:12:30-03:00",
  "last_progress_at": "2026-08-31T23:10:08-03:00"
}
```

Não é necessário preencher tudo em todos os eventos.

---

## 5. Eventos mínimos do ciclo completo

### Painel / fila

- `JOB_REQUEST_RECEIVED`
- `JOB_VALIDATED`
- `BATCH_CREATED`
- `WINDOW_CREATED`
- `DUPLICATE_ACTIVE_JOB_DETECTED`
- `QUEUE_LOCK_WAIT`
- `QUEUE_LOCK_ACQUIRED`
- `QUEUE_LOCK_RELEASED`
- `JOB_QUEUED`
- `JOB_DISPATCHED`
- `JOB_RESUMED`
- `JOB_RETRY_CREATED`
- `BATCH_PAUSED`
- `BATCH_RESUMED`
- `PENDING_WINDOWS_CANCELLED`

### Bridge / worker

- `WORKER_PROCESS_STARTING`
- `WORKER_PROCESS_STARTED`
- `WORKER_HEARTBEAT`
- `WORKER_PROGRESS`
- `WORKER_EXITED`
- `WORKER_EXIT_UNEXPECTED`
- `WORKER_HEARTBEAT_LOST`
- `WATCHDOG_TIMEOUT`
- `WATCHDOG_TERMINATE_SENT`
- `WATCHDOG_KILL_SENT`
- `ORPHAN_JOB_DETECTED`

### Robô / Playwright

- `ROBOT_STARTING`
- `BROWSER_STARTING`
- `BROWSER_STARTED`
- `SSW_OPENING`
- `SSW_OPENED`
- `AUTHENTICATING`
- `AUTHENTICATION_STEP_COMPLETED`
- `OPTION_036_OPENING`
- `OPTION_036_OPENED`
- `REPORT_FIELDS_FILLING`
- `REPORT_FIELDS_FILLED`
- `REPORT_REQUESTING`
- `REPORT_REQUESTED`
- `WAITING_DOWNLOAD_STARTED`
- `DOWNLOAD_STARTED`
- `DOWNLOAD_COMPLETED`
- `FILE_HASH_CALCULATED`
- `ROBOT_COMPLETED`
- `BROWSER_CLOSED`

### Importador

- `VALIDATION_STARTED`
- `VALIDATION_COMPLETED`
- `PARSER_STARTED`
- `PARSER_COMPLETED`
- `NORMALIZATION_STARTED`
- `NORMALIZATION_COMPLETED`
- `IMPORT_LOCK_WAIT`
- `IMPORT_LOCK_ACQUIRED`
- `DB_TRANSACTION_STARTED`
- `DB_APPLY_COMPLETED`
- `DB_TRANSACTION_COMMITTED`
- `DB_TRANSACTION_ROLLBACK`
- `IMPORT_COMPLETED`

---

## 6. Medição de duração por etapa

Toda etapa deve registrar início e fim.

Exemplo:

```text
AUTHENTICATING               1.284 ms
OPTION_036_OPENING           2.901 ms
REPORT_FIELDS_FILLING          184 ms
REPORT_REQUESTING              422 ms
WAITING_DOWNLOAD           183.114 ms
VALIDATING                      96 ms
PARSER                        1.248 ms
NORMALIZATION                 2.712 ms
DB_APPLY                     18.831 ms
```

Isso permite identificar imediatamente se a lentidão está:

- no SSW;
- no navegador;
- no download;
- no parser;
- na normalização;
- no lock;
- no banco.

---

## 7. Heartbeat e detecção de travamento

Enquanto o worker estiver vivo, o orquestrador deve receber/gravar heartbeat periódico.

Campos:

```json
{
  "event": "WORKER_HEARTBEAT",
  "execution_id": "SSW-...",
  "worker_pid": 13844,
  "stage": "WAITING_DOWNLOAD",
  "stage_elapsed_ms": 91000,
  "last_progress_at": "...",
  "browser_alive": true
}
```

### Regra

Diferenciar:

- processo vivo e progredindo;
- processo vivo mas sem progresso;
- processo morto;
- browser morto;
- callback parado;
- SSW demorando dentro de uma etapa conhecida.

---

## 8. Watchdog

Quando o limite externo for atingido, gravar antes de encerrar:

```json
{
  "level": "ERROR",
  "event": "WATCHDOG_TIMEOUT",
  "error_code": "ROBOT_HARD_TIMEOUT",
  "execution_id": "SSW-...",
  "stage": "WAITING_DOWNLOAD",
  "stage_elapsed_ms": 301442,
  "hard_timeout_ms": 300000,
  "worker_pid": 13844,
  "browser_pid": 19420,
  "last_heartbeat_at": "...",
  "last_progress_at": "...",
  "retryable": true,
  "queue_action": "PAUSE_BATCH"
}
```

Depois registrar separadamente:

- `WATCHDOG_TERMINATE_SENT`
- resultado da tentativa de terminate;
- `WATCHDOG_KILL_SENT`, se necessário;
- `WORKER_EXITED`;
- liberação do lock;
- estado final do job;
- estado final do batch.

Nunca escrever apenas "timeout".

---

## 9. Códigos de erro mais específicos

Preservar os códigos existentes e acrescentar códigos de diagnóstico:

### Configuração / contrato

- `CONFIG_ERROR`
- `INVALID_JOB`

### SSW / navegador

- `SSW_OPEN_TIMEOUT`
- `SSW_UNAVAILABLE`
- `AUTH_OR_OPTION_TIMEOUT`
- `LOGIN_REJECTED`
- `OPTION_036_TIMEOUT`
- `POPUP_TIMEOUT`
- `SELECTOR_TIMEOUT`
- `REPORT_REQUEST_TIMEOUT`
- `DOWNLOAD_TIMEOUT`
- `DOWNLOAD_FAILED`
- `BROWSER_CRASH`
- `BROWSER_CLOSED_UNEXPECTEDLY`
- `ROBOT_UNEXPECTED`

### Processo / orquestração

- `ROBOT_HARD_TIMEOUT`
- `WORKER_PROCESS_LOST`
- `WORKER_HEARTBEAT_LOST`
- `WORKER_EXIT_NONZERO`
- `ORPHAN_RUNNING_JOB`
- `QUEUE_LOCK_TIMEOUT`
- `IMPORT_LOCK_TIMEOUT`
- `DUPLICATE_JOB_BLOCKED`

### Arquivo / importação

- `FILE_NOT_FOUND`
- `EMPTY_DOWNLOAD`
- `FILE_HASH_ERROR`
- `INVALID_REPORT_STRUCTURE`
- `INVALID_REPORT_PERIOD`
- `PARSER_ERROR`
- `NORMALIZATION_ERROR`
- `DB_LOCKED`
- `DB_TRANSACTION_ERROR`
- `IMPORT_UNEXPECTED`

---

## 10. Estrutura obrigatória de erro

Todo erro deve possuir:

```json
{
  "error_code": "DOWNLOAD_TIMEOUT",
  "exception_type": "PlaywrightTimeoutError",
  "error_message": "Download não iniciou dentro do limite.",
  "stage": "WAITING_DOWNLOAD",
  "operation": "page.expect_download",
  "timeout_ms": 180000,
  "retryable": true,
  "suggested_action": "Reprocessar somente esta janela após confirmar disponibilidade do SSW.",
  "evidence": [
    "evidence_001.png",
    "traceback.txt"
  ]
}
```

`error_message`, `traceback` e evidências precisam ser sanitizados.

---

## 11. Capturar a última ação conhecida

Antes de cada operação importante, gravar `operation`.

Exemplos seguros:

```text
page.goto(SSW_URL)
click(login_submit)
fill(option_field, "036")
press(option_field, "Enter")
wait_for_popup(option_036)
fill(t_excel, "S")
fill(t_unidade, "BEL")
fill(t_dt_ini, "010826")
fill(t_dt_fin, "310826")
click(btn_env_periodo)
expect_download()
save_as(...)
```

Nunca registrar senha, cookie, token ou valor de campos de autenticação.

---

## 12. Diagnóstico automático final

Ao terminar, criar `diagnostic.json`.

### Falha exemplo

```json
{
  "execution_id": "SSW-20260831-00125",
  "result": "ERROR",
  "error_code": "ROBOT_HARD_TIMEOUT",
  "failed_component": "robot_ssw",
  "failed_stage": "WAITING_DOWNLOAD",
  "last_successful_stage": "REPORT_REQUESTED",
  "total_elapsed_ms": 307882,
  "failed_stage_elapsed_ms": 301442,
  "last_heartbeat_age_ms": 4012,
  "worker_pid": 13844,
  "browser_pid": 19420,
  "worker_was_killed": true,
  "lock_released": true,
  "batch_paused": true,
  "completed_windows_preserved": true,
  "retryable": true,
  "probable_cause": "SSW não iniciou o download dentro do tempo máximo.",
  "recommended_action": "Verificar disponibilidade do SSW e reprocessar somente a janela 01/08/2026–31/08/2026."
}
```

Esse arquivo deve ser gerado automaticamente; não depender de análise humana.

---

## 13. Resumo legível no Histórico do Robô

Na tela de detalhes:

```text
Execução: SSW-20260831-00125
Lote: BATCH-20260831-00004
Período: 01/08/2026 → 31/08/2026
Tentativa: 1
Resultado: ERRO
Código: ROBOT_HARD_TIMEOUT

Última etapa concluída:
✓ Relatório solicitado

Falha em:
✕ Aguardando download

Tempo nessa etapa:
5m 01s

Último heartbeat:
4s antes do encerramento

Worker:
PID 13844 — encerrado pelo watchdog

Browser:
PID 19420

Fila:
PAUSADA

Períodos anteriores:
PRESERVADOS

Lock:
LIBERADO

Diagnóstico provável:
SSW não iniciou o download dentro do limite.

Ação sugerida:
Verificar o SSW e reprocessar somente esta janela.
```

Botões:

- `Ver linha do tempo`
- `Baixar pacote de diagnóstico`
- `Ver evidência`
- `Reprocessar esta janela`
- `Retomar fila`

---

## 14. Linha do tempo

Exemplo:

```text
23:05:01.104  JOB_QUEUED
23:05:01.381  WORKER_PROCESS_STARTED       PID 13844
23:05:02.024  BROWSER_STARTED              PID 19420
23:05:03.812  SSW_OPENED
23:05:05.104  AUTHENTICATING
23:05:07.842  OPTION_036_OPENED
23:05:08.151  REPORT_FIELDS_FILLED
23:05:08.594  REPORT_REQUESTED
23:05:08.595  WAITING_DOWNLOAD_STARTED
23:06:08.603  WORKER_HEARTBEAT             60s aguardando
23:07:08.618  WORKER_HEARTBEAT            120s aguardando
23:08:08.634  WORKER_HEARTBEAT            180s aguardando
23:10:10.037  WATCHDOG_TIMEOUT             301s
23:10:10.081  WATCHDOG_TERMINATE_SENT
23:10:11.326  WORKER_EXITED
23:10:11.401  QUEUE_LOCK_RELEASED
23:10:11.460  BATCH_PAUSED
23:10:11.502  JOB_FINISHED_ERROR
```

---

## 15. Pacote de diagnóstico

Criar ação **Baixar pacote de diagnóstico**.

ZIP:

```text
diagnostico_SSW-20260831-00125.zip
├── events.jsonl
├── robot.log
├── status.json
├── result.json
├── diagnostic.json
├── traceback.txt
├── evidence_001.png
└── environment.json
```

`environment.json` pode conter:

- versão do Painel;
- hash/build do core homologado;
- versão do Import Engine;
- versão Python;
- versão Playwright;
- navegador/versão;
- hostname;
- sistema operacional;
- configuração de timeout sem credenciais;
- banco utilizado (SQLite/PostgreSQL);
- PID do processo.

Não incluir `.env`.

---

## 16. Logging de fila e reprocessamento

Registrar explicitamente:

```text
BATCH_CREATED
WINDOW_CREATED
WINDOW_ALREADY_SUCCESS
WINDOW_SKIPPED_COMPLETED
WINDOW_RETRY_CREATED
WINDOW_ERROR
BATCH_PAUSED
BATCH_RESUMED
```

Exemplo:

```json
{
  "event": "WINDOW_SKIPPED_COMPLETED",
  "batch_id": "BATCH-...",
  "start_date": "2026-07-01",
  "end_date": "2026-07-31",
  "previous_execution_id": "SSW-...",
  "previous_status": "SUCCESS",
  "reason": "Período já concluído; não será colocado novamente na fila."
}
```

Isso deixa prova de que o sistema não reprocessou silenciosamente períodos concluídos.

---

## 17. Logging de locks

Para cada lock:

```text
LOCK_WAIT_STARTED
LOCK_ACQUIRED
LOCK_RELEASED
LOCK_TIMEOUT
```

Registrar:

- nome/chave;
- PID que possui o lock quando detectável;
- tempo de espera;
- execution_id;
- batch_id;
- motivo;
- tempo total segurando lock.

Isso é essencial para diferenciar "SSW travou" de "o sistema está aguardando um lock".

---

## 18. Logging do Import Engine

Registrar pelo menos:

- arquivo;
- tamanho;
- SHA-256;
- linhas físicas;
- linhas válidas;
- linhas inválidas;
- CT-es distintos;
- ocorrências;
- motoristas;
- clientes;
- retenções;
- rotas;
- inseridos;
- atualizados;
- ignorados;
- sem alteração;
- warnings;
- duração de parser;
- duração de normalização;
- duração de comparação;
- duração de persistência;
- duração da transação.

Não imprimir milhares de linhas individuais no log principal. Exemplos de linhas inválidas devem ser limitados.

---

## 19. Níveis

### DEBUG
Detalhes técnicos úteis em desenvolvimento.

### INFO
Fluxo normal e transições.

### WARNING
Situação anormal recuperável.

### ERROR
Execução ou etapa falhou.

### CRITICAL
Falha estrutural que ameaça fila/worker/orquestrador, por exemplo:
- watchdog não conseguiu matar processo;
- lock não pôde ser liberado;
- corrupção de estado;
- worker zumbi reincidente.

---

## 20. Sanitização

Antes de persistir qualquer texto:

- substituir senha conhecida;
- substituir tokens;
- substituir cookies;
- não guardar `page.content()` completo;
- não guardar headers de autenticação;
- não guardar `.env`;
- não registrar valores dos campos de login.

Traceback deve ser sanitizado antes de ser salvo.

---

## 21. Rotação e retenção

Sugestão inicial:

- execuções com SUCCESS: 30 dias de logs técnicos locais;
- WARNING/ERROR: 90 dias;
- metadados do `ImportRun`: permanentes conforme política do sistema;
- evidências/screenshot: acesso restrito e retenção configurável.

Os números devem ser configuração, não hardcode espalhado.

---

## 22. Critérios de aceite

A implementação só está concluída quando estes testes passarem:

1. SSW abre normalmente → log completo até SUCCESS.
2. Login trava → erro mostra etapa exata.
3. Popup 036 não abre → `POPUP_TIMEOUT`.
4. Botão do relatório não responde → erro específico.
5. Download nunca começa → `DOWNLOAD_TIMEOUT`.
6. `run_job()` fica travado → watchdog gera `ROBOT_HARD_TIMEOUT`.
7. Worker morre → `WORKER_PROCESS_LOST`.
8. Heartbeat some com processo ainda presente → `WORKER_HEARTBEAT_LOST`.
9. Browser fecha sozinho → `BROWSER_CRASH`/equivalente.
10. Importação trava por lock → log diferencia `IMPORT_LOCK_WAIT`.
11. SQLite/PostgreSQL falha → `DB_TRANSACTION_ERROR`, rollback registrado.
12. Reprocessar janela falha não recoloca janelas SUCCESS.
13. Reiniciar aplicação com job RUNNING órfão → `ORPHAN_RUNNING_JOB`.
14. Nenhum segredo aparece em logs, traceback, JSON ou screenshot de login.
15. O Histórico consegue mostrar `last_successful_stage`, `failed_stage`, duração e ação recomendada.

---

## 23. Regra final

O objetivo do novo logging é permitir que, ao receber apenas o `execution_id`, o desenvolvedor consiga responder:

1. O que o usuário pediu?
2. Em qual lote/janela estava?
3. Qual processo executou?
4. Até onde chegou?
5. Qual foi a última ação bem-sucedida?
6. Onde travou?
7. Quanto tempo ficou parado?
8. O processo continuava vivo?
9. O navegador continuava vivo?
10. O watchdog interveio?
11. Qual foi o código técnico?
12. Houve traceback/evidência?
13. O lock foi liberado?
14. A fila foi pausada?
15. Os períodos concluídos foram preservados?
16. É seguro dar retry?
17. Qual janela deve ser reprocessada?
18. O banco foi alterado ou houve rollback?

Se o log não conseguir responder a essas perguntas, ele ainda não é suficientemente diagnóstico.
