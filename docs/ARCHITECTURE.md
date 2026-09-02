# Arquitetura — V0.2.1

## Princípio
O sistema orquestra; o robô SSW executa.

## Camadas
- UI server-rendered: Django Templates + JavaScript leve.
- Backend: Django.
- Dados: PostgreSQL oficial; SQLite apenas em homologação local rápida.
- Jobs: Celery + Redis na arquitetura alvo.
- Automação SSW: Playwright.

## Fluxo de dados

```text
SSW
→ relatório .sswweb/.csv
→ importação individual ou lote mensal
→ parser/normalização
→ deduplicação e histórico
→ PostgreSQL/SQLite
→ data operacional por SAIDA PARA ENTREGA
→ indicadores/rotas/comprovantes
→ telas e relatórios
```

## Regra temporal
A data de emissão do romaneio e a data operacional são conceitos separados. `SAIDA PARA ENTREGA` (código 85) materializa a execução da rota e é preservada no histórico.

## Importação em lote
`import_ssw_batch` ordena relatórios pelo período detectado e processa cada arquivo de forma isolada, preservando importações concluídas caso um item do lote falhe.


## Homologação integrada — V0.2.2
`apps/bugs` é o módulo de QA interno. Ele não interfere nas regras SSW/operacionais: registra defeitos do produto, evidências e ciclo de correção/reteste. Os anexos usam `MEDIA_ROOT`; criação e edição alimentam `AuditLog`.

## Integração SSW homologada — v0.2.2-p13
O executor Playwright homologado é um componente encapsulado em `robot_ssw/robot_ssw/` e expõe `run_job(payload, status_callback)`. O Django não contém seletores SSW. O processo local `manage.py run_ssw_robot <id>` chama essa API e traduz apenas eventos técnicos para `ImportRun/ImportStep`. Após `DOWNLOADED`, o controle volta ao importador do Painel, que executa validação, normalização, idempotência e gravação operacional.

O patch p13 remove o executor experimental do caminho ativo e preserva a versão anterior em backup. `HOMOLOGATED_CORE.sha256` permite verificar que o core original não foi modificado pela integração.


## Performance layer v0.3.0
O pipeline de importação agora é explicitamente separado do robô. `robot_ssw.run_job()` termina em `DOWNLOADED`; o Painel entrega o arquivo ao Import Engine v2. Views críticas usam serviços/preloads e o cache padrão local não é requisito de consistência para rotas/comprovantes.

## Arquitetura VPS v0.8.0.0

```text
Internet -> Nginx :80 -> Django/Gunicorn -> PostgreSQL
                         |      |
                         |      +-> Redis <- Celery Worker / Beat
                         |                    |
                         |                    +-> fila ssw -> robot-worker (Playwright 036)
                         |
                         +-> API interna <- Baileys/Node
```

Banco, Redis, media, inbox/importações e `local_data` são volumes persistentes. Containers usam `restart: unless-stopped` para boot automático.
