# Robô SSW — Painel Motoristas

Executor Playwright da opção **036 — Consulta e Reimpressão de Romaneios**.

## Regra de arquitetura

- Painel Motoristas = orquestrador.
- Robô SSW = executor.
- O robô não importa, deduplica, calcula indicadores ou grava nas tabelas operacionais.
- `DOWNLOADED` não é `SUCCESS`: depois do download o Painel ainda valida/processa/aplica.

## Instalação

1. Execute `install.bat`.
2. Abra `.env` e preencha uma única vez empresa, CPF, usuário e senha.
3. Teste o contrato com `py contract_test.py`.
4. Teste real com `py run_robot.py --job job_example.json`.

## Contrato mínimo Painel -> Robô

```json
{
  "execution_id": "SSW-20260831-00125",
  "start_date": "2026-08-01",
  "end_date": "2026-08-31",
  "mode": "INCREMENTAL",
  "requested_by": "system"
}
```

Unidade, relatório e pasta têm valores padrão no `.env`, mas continuam aceitos no payload para compatibilidade com a arquitetura alvo.

O executor recusa janelas acima de `ROBOT_MAX_DAYS` (31 por padrão). A quebra mensal é responsabilidade do Painel.

## Estados do robô

`ROBOT_STARTING -> AUTHENTICATING -> REQUESTING_REPORT -> WAITING_DOWNLOAD -> DOWNLOADED`

Em falha: `ERROR`.

`VALIDATING`, `PROCESSING`, `APPLIED`, `SUCCESS` e `WARNING` são estados do Painel/importador.

## Integração Python

```python
from robot_ssw import run_job

result = run_job({
    "execution_id": "SSW-20260831-00125",
    "start_date": "2026-08-01",
    "end_date": "2026-08-31",
    "mode": "INCREMENTAL",
    "requested_by": "system",
})
```

Veja também `integration_example.py` para usar `status_callback` e refletir o progresso em `ImportRun/ImportStep`.

## Comportamentos do SSW já confirmados

- Login: clique no `►`.
- Menu: preencher `036` e pressionar Enter.
- 036: `#t_excel=S`, unidade, datas `DDMMAA`.
- Geração: `#btn_env_periodo.click()`.
- O download é capturado diretamente pelo Playwright.

## Saída por execução

Cada execução possui diretório isolado com:

- `relatorio_036.<extensão>`
- `status.json`
- `result.json`
- `robot.log`
- `evidence_*.png` quando houver falha e for possível gerar evidência.
