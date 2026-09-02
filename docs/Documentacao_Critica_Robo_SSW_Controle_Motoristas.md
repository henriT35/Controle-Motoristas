# Documentação Crítica — Robô SSW — Controle dos Motoristas

## Regra-mãe
**Painel Motoristas = ORQUESTRADOR. Robô SSW = EXECUTOR.**

O robô somente autentica no SSW, abre a opção 036, preenche a consulta, solicita o relatório, captura o download e devolve arquivo + metadados. Regras de negócio, deduplicação, histórico, rotas, comprovantes, indicadores e gravações operacionais permanecem no Painel.

## Pontos que não podem ser quebrados
- Opção usada: **036 — Consulta e Reimpressão de Romaneios**.
- Rotina atual: **Excel = S** e unidade padrão **BEL**.
- No menu do SSW: `fill("036")` **não basta**; precisa `press("Enter")`.
- No botão da consulta: usar `#btn_env_periodo.click()`; Enter não foi confiável.
- A 036 abre em popup; usar `expect_popup()`.
- Datas no SSW: `DDMMAA`.
- Download deve ser capturado por `expect_download()`, não por varredura manual da pasta Downloads.
- Credenciais ficam em `.env`; nunca hardcoded ou em log.
- Cada execução usa `execution_id` único e pasta isolada.
- O robô não escreve diretamente no PostgreSQL operacional.
- `DOWNLOADED` não é `SUCCESS`.
- O Painel quebra períodos grandes; o pacote atual rejeita janelas acima de 31 dias.

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

## API Python de integração
```python
from robot_ssw import run_job

resultado = run_job(payload, status_callback=atualizar_status_da_execucao)
```

O callback deve atualizar somente o estado de ImportRun/ImportStep ou equivalente. Não deve usar eventos do Playwright para alterar CT-es, rotas ou comprovantes.

## Estados
Robô: `ROBOT_STARTING -> AUTHENTICATING -> REQUESTING_REPORT -> WAITING_DOWNLOAD -> DOWNLOADED` ou `ERROR`.

Painel: `QUEUED`, depois do download `VALIDATING -> PROCESSING -> APPLIED -> SUCCESS/WARNING`.

## Saída por execução
```text
imports/
└── inbox/
    └── <execution_id>/
        ├── relatorio_036.<extensão original>
        ├── status.json
        ├── result.json
        ├── robot.log
        └── evidence_*.png
```

## Regras de segurança
- Nunca colocar senha, token ou cookie em log/result.json.
- Nunca hardcodar credenciais no worker.
- Nunca fazer SQL operacional direto no robô.
- Evidência técnica deve ser sanitizada e ter acesso restrito.

## Erros atuais relevantes
`CONFIG_ERROR`, `INVALID_JOB`, `AUTH_OR_OPTION_TIMEOUT`, `DOWNLOAD_TIMEOUT`, `DOWNLOAD_FAILED`, `FILE_NOT_FOUND`, `EMPTY_DOWNLOAD`, `SELECTOR_TIMEOUT`, `ROBOT_UNEXPECTED`.

Qualquer erro do robô deve impedir importação/aplicação de banco daquela execução.

## Homologação obrigatória
Antes de produção, provar ponta a ponta: Painel cria job -> robô recebe -> login -> 036+Enter -> preenche S/BEL/período -> click -> download -> arquivo isolado -> SHA-256 -> DOWNLOADED -> Painel valida/processa -> SUCCESS/WARNING.

## Diretriz ao agente
Se uma alteração fizer o robô decidir regra de negócio, calcular status operacional, deduplicar domínio ou gravar tabelas operacionais, essa alteração está no componente errado.
