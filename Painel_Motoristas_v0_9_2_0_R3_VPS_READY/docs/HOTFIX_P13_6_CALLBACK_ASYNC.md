# Hotfix p13.6 — Callback Playwright x ORM Django

## Sintoma

A execução falhava logo após `ROBOT_STARTING` com:

```text
You cannot call this from an async context - use a thread or sync_to_async.
```

## Causa

O core homologado usa `playwright.sync_api`. Apesar da API ser síncrona para o chamador, o Playwright mantém um loop asyncio/greenlet internamente. O `status_callback` era chamado a partir desse contexto e fazia ORM Django diretamente (`ImportRun.save`, `ImportStep`). O Django detectava o loop ativo e lançava `SynchronousOnlyOperation`.

## Correção

O core homologado **não foi alterado**.

A ponte do Painel agora usa `RobotEventPump`:

```text
Playwright / core homologado
        ↓ status_callback
Queue thread-safe (sem ORM)
        ↓
Thread Django dedicada
        ↓
ImportRun / ImportStep
```

O callback chamado pelo Playwright somente executa `queue.put(event)`. Uma thread separada, com conexão Django própria, persiste o progresso.

## Preservado

- `robot_ssw.run_job()`
- login homologado
- `036 + Enter`
- `expect_popup()`
- `#t_excel=S`
- `#t_unidade=BEL`
- datas `DDMMAA`
- `#btn_env_periodo.click()`
- `expect_download()`
- `DOWNLOADED != SUCCESS`

## Arquivos alterados

- `apps/ssw/robot_service.py`
- `apps/ssw/robot_bridge.py` (somente build + correção p13.5 preservada)

## Build

`0.2.2-p13.6`
