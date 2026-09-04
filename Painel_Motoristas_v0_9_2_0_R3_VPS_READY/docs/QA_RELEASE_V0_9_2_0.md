# QA release — v0.9.2.0

**Projeto:** Controle dos Motoristas  
**Versão:** v0.9.2.0  
**Baseline de origem:** v0.9.1.0 corrigida/hotfixada  
**Data:** 03/09/2026  
**Tipo:** Avaliação V3 definitiva + transparência + retenções + Portal + auditoria

## 1. Status da candidata

A v0.9.2.0 foi construída sobre a baseline v0.9.1.0 corrigida. O QA portátil/estático disponível neste ambiente foi executado, incluindo regressão com os relatórios SSW reais fornecidos nesta rodada. O core `robot_ssw/` foi comparado integralmente com a baseline de origem e permaneceu idêntico.

Há **HOMOLOGAÇÃO EXTERNA PENDENTE** para tudo que depende do runtime Django instalado, migrations executadas em banco, PostgreSQL real, navegador/viewport real, SSW real, WhatsApp real e Docker/VPS.

## 2. QA realmente executado — PASS

| Verificação | Resultado real |
|---|---|
| `python -m compileall -q .` | PASS |
| `scripts/qa/portable_qa.py` | PASS — 221 arquivos Python; 6/6 invariantes |
| migrations v0.9.1 — contrato estático | PASS |
| migrations v0.9.2 — contrato estático | PASS — novos models/campos/índices versionados conferidos |
| fórmula/performance legado + V3 | PASS |
| performance/importador — contrato estático | PASS |
| regressão real de retenções v0.9.2 | PASS — 12 relatórios, 27.126 linhas |
| BNU046259-4 | PASS — ROM34 histórico + CTRC atual `1 ENTREGUE` = resolvido |
| CWB055520-7 | PASS — ROM34 histórico + CTRC atual `1 ENTREGUE`, mesmo com correção retroativa de data = resolvido |
| robot adapter / manifesto do core | PASS — 6/6 hashes internos |
| mock opção 036 | PASS — login mock → 036 → S/BEL/período → download |
| decorators SSW | PASS |
| templates/rotas | PASS — 71 nomes conhecidos; 0 referência estática órfã |
| temporal v0.9.1/v0.9.2 | PASS |
| contrato v0.9.1 | PASS |
| contrato v0.9.2 | PASS — ROM13 manual, Regularidade real, Portal explicável e retenção por estado atual |
| fórmula v0.9.2 | PASS — 50/2=96,0%; 300/12=96,0%; 300/2=99,3%; Regularidade 18/20=90% |
| VPS — contrato estático | PASS |
| WhatsApp Baileys — contrato estático | PASS |
| telefone BR com/sem 9 | PASS |
| `node --check` | PASS — 2 arquivos JS/MJS |
| `bash -n` | PASS — 7 scripts shell |
| `robot_ssw/` x baseline v0.9.1.0 | PASS — 17/17 arquivos; 0 diferenças de caminho; 0 diferenças SHA-256 |

## 3. Regressões da avaliação V3 cobertas

O QA estático/fórmula verifica, entre outros:

- ROM13 pendente não penaliza;
- somente ROM13 validado como `DRIVER_RESPONSIBLE` entra na Qualidade;
- ROM13 `NOT_RESPONSIBLE` e `VERIFY` são neutros;
- ROM34 não entra na Qualidade;
- mesma tentativa + mesmo ROM13 é idempotente;
- nova tentativa + novo ROM13 pode gerar nova penalização independente;
- Qualidade é proporcional ao volume de tentativas, sem bônus por produtividade;
- Regularidade usa ações obrigatórias apresentadas/cumpridas;
- Retirada Exata sem manifestação pode virar omissão;
- Ouro ignorado permanece neutro;
- `AINDA NÃO LIBERADO` e `NÃO FOI POSSÍVEL TENTAR` exigem manifestação/justificativa conforme fluxo;
- projeção do Portal usa a mesma fórmula V3 e respeita teto de bônus;
- `original_driver` e `recovery_driver` permanecem independentes.

## 4. Regressões de retenção/SSW cobertas

- ROM34 é origem histórica da retenção;
- CTRC atual `34` mantém retenção ativa;
- CTRC atual `1/ENTREGUE` encerra automaticamente a retenção;
- resolução automática SSW não cria `recovery_driver`, não cria `confirmed_by` e não concede bônus;
- CTRC atual `60`, `53`, `91` ou outro não conclusivo entra em `ACOMPANHANDO_SSW`;
- `ACOMPANHANDO_SSW` pode resolver quando o estado atual virar `1/ENTREGUE`;
- pode reativar retenção se o estado atual voltar a `34`;
- horário/data técnica inferida não bloqueia uma baixa atual por `ENTREGUE`;
- snapshot importado fora de ordem não pode regredir um estado atual pertencente a tentativa operacional mais nova;
- reconciliação foi implementada com modo `--dry-run` e desenho idempotente/auditável.

## 5. Dados reais utilizados nesta rodada

Foram usados **12 relatórios SSW reais**, totalizando **27.126 linhas**, somente para QA privado desta execução. Esses arquivos **não fazem parte da release** e não devem ser publicados no GitHub.

Casos de regressão confirmados:

### BNU046259-4

- retenção histórica ROM34;
- data/hora ROM histórica ausente/inferível;
- estado consolidado atual CTRC `1 — ENTREGUE`;
- resultado esperado e obtido no parser: retenção não ativa / resolvida.

### CWB055520-7

- retenção histórica ROM34;
- estado consolidado atual CTRC `1 — ENTREGUE`;
- existe correção retroativa de data no SSW, portanto a simples comparação cronológica seria enganosa;
- resultado esperado e obtido: retenção não ativa / resolvida.

## 6. Comandos tentados, mas indisponíveis neste ambiente

Os comandos abaixo foram executados e falharam **antes de carregar a aplicação**, pois o Python deste ambiente não possui Django:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Erro real nos três casos:

```text
ModuleNotFoundError: No module named 'django'
```

Portanto esses itens **não são PASS**.

Também não existe binário Docker neste ambiente, então `docker compose config` não pôde ser executado. O contrato VPS foi validado apenas estaticamente.

## 7. HOMOLOGAÇÃO EXTERNA PENDENTE

Executar antes de promover para produção:

1. `python manage.py check` em ambiente com dependências instaladas;
2. `python manage.py makemigrations --check --dry-run` e exigir `No changes detected`;
3. `python manage.py migrate --plan`;
4. migration em SQLite limpo;
5. migration em cópia do banco SQLite/PostgreSQL existente;
6. suíte Django completa;
7. `reconcile_retained_proofs --dry-run` no banco real e revisão do resumo antes da aplicação;
8. teste real do Portal por token, inclusive isolamento entre motoristas;
9. validação visual 1920x1080, 1366x768, 1280x720, 1024, tablet e mobile;
10. SSW 036 real no Windows/VPS com scheduler/fila/lock;
11. Baileys real com celular, QR e envio;
12. Docker Compose na VPS e reboot com `restart: unless-stopped`;
13. benchmark HTTP real com cache frio/quente em Dashboard, Operação, Ranking, Portal, Comprovantes e Central de Avaliações.

## 8. Critério de promoção

Esta release pode ser empacotada como candidata porque a implementação, os contratos portáteis, as regressões privadas disponíveis e o patch dry-run são verificáveis. Ela **não deve ser chamada de homologada em produção** até os itens externos acima serem concluídos.
## 9. Patch dry-run

O patch foi gerado contra uma cópia limpa da baseline v0.9.1.0 corrigida e **aplicado a partir do ZIP extraído**, não da árvore de desenvolvimento. Resultado da comparação contra a baseline v0.9.2.0:

- arquivos na origem: **507**;
- arquivos na v0.9.2.0: **531**;
- adicionados: **24**;
- modificados: **55**;
- removidos: **0**;
- diferenças de caminhos após aplicar o patch: **0**;
- diferenças SHA-256/conteúdo após aplicar o patch: **0**.

O aplicador valida `VERSION=0.9.1.0`, verifica SHA-256 de todos os arquivos de origem modificados/deletados antes de alterar a árvore e valida os hashes do payload após a cópia.



## 10. Hotfix de system check confirmado no Windows

Na primeira execução real da baseline v0.9.2.0 no Windows, o Django bloqueou a validação antes das migrations com:

```text
proofs.ProofPickupOpportunity: (models.E034) The index name 'proofs_opp_driver_date_kind_idx' cannot be longer than 30 characters.
```

Causa: o nome explícito do índice tinha **31 caracteres**. A correção mantém os mesmos campos (`driver`, `operation_date`, `kind`) e apenas renomeia o índice para `proofs_opp_drv_date_kind_idx` (**28 caracteres**) no model e na migration versionada.

Após a correção, foi executada validação estática de todos os `models.Index(..., name=...)` do projeto e nenhum nome permanece acima de 30 caracteres. Os contratos estáticos de migrations/versão também passaram. O `manage.py check` completo ainda deve ser reexecutado no Windows do usuário, que possui o ambiente Django real.
