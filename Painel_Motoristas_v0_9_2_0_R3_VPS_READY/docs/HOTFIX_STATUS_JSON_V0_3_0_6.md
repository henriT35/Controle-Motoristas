# Hotfix v0.3.0.6 — Windows file lock / status.json

Data: 2026-09-01

## Problema observado

Em uma execução mensal do robô SSW, o Windows retornou `WinError 5 - Acesso negado`
na troca atômica de `status.json.tmp` para `status.json`. Como o core homologado
escrevia o status antes de continuar a etapa, a falha de telemetria era convertida
em `ROBOT_UNEXPECTED` e a fila mensal era pausada.

Exemplo de causa registrada:

`status.json.tmp -> status.json: [WinError 5] Acesso negado`

## Regra corrigida

`status.json` é telemetria. Falha de atualização desse snapshot **não pode cancelar
uma automação SSW funcional**.

## Solução

- o core homologado em `robot_ssw/` permanece byte a byte inalterado;
- a bridge do Painel instala em runtime uma camada de escrita resiliente ao redor
  da função JSON do executor;
- temporário fixo `status.json.tmp` deixa de ser usado em runtime e passa a ser
  um nome exclusivo por PID, thread e UUID;
- `os.replace()` recebe até 12 tentativas para bloqueios transitórios do Windows
  (`WinError 5`, sharing violation e lock violation);
- o atraso entre tentativas é curto e progressivo, limitado a 500 ms;
- se `status.json` continuar bloqueado após todos os retries, a falha é registrada
  como warning técnico e o robô continua;
- quando possível, o snapshot que não conseguiu substituir o destino é preservado
  em `status.json.write_failed.<...>.json` para investigação;
- `result.json` também recebe temporário exclusivo e retry, mas permanece obrigatório:
  uma falha definitiva desse arquivo continua sendo erro, pois o resultado final
  não deve ser mascarado;
- `worker_state.json`, `diagnostic.json`, `environment.json`, `events.jsonl` e
  `orchestrator.log` também foram tornados best-effort para observabilidade nunca
  derrubar o watchdog.

## Compatibilidade

O patch é cumulativo e aceita como base:

- `0.3.0.4`; ou
- `0.3.0.5`.

Quando aplicado diretamente sobre `0.3.0.4`, ele também inclui as correções do
Dashboard Evolution Hotfix v0.3.0.5.

Não há migration de banco.

## Comportamento após aplicar

Se a fila estiver pausada por causa do erro antigo, use **Retomar fila**. As janelas
que já estavam concluídas continuam preservadas e a próxima pendente/erro é
processada sem recriar o lote inteiro.

## Validação do pacote

- `compileall` estático: obrigatório no instalador;
- `scripts/qa_status_json_v0306.py`: simula WinError 5 transitório e permanente;
- integridade de `robot_ssw/`: o patch não contém arquivos dessa pasta;
- teste real SSW/Windows: deve ser executado no ambiente operacional.
