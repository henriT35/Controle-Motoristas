# Bugs — causa raiz e correções v0.5.0.0

| ID | Status | Causa raiz / evidência | Correção | Teste |
|---|---|---|---|---|
| BUG-001 — execução SSW eterna | **CONFIRMADO / corrigido no código** | `DISPATCHED` sem `worker_state/heartbeat` não tinha encerramento curto e a reconciliação não era acionada de forma suficientemente frequente pela UI | timeout de despacho, heartbeat, PID perdido, órfão, polling com reconciliação e códigos de erro | testes Django adicionados; **não executados aqui** |
| BUG-002 — relatórios zerados/vazios | **CONFIRMADO parcialmente / corrigido no código** | período selecionado não era preservado explicitamente em todos os links de preview/PDF/XLSX; havia risco de cair no período padrão | período único via `parse_period`, query preservada e datasets históricos | teste de propagação adicionado; **não executado aqui** |
| BUG-003 — mapa abre somente Belém | **CONFIRMADO como lacuna de fallback** | drill-down de bairros depende de fonte geográfica disponível; município sem malha podia não oferecer detalhe útil | município com bairros abre bairros; sem malha abre detalhe municipal/regional em vez de clique silencioso | testes geo existentes/adicionados; **não executados aqui** |
| BUG-004 — Tapanã/dado sem polígono | **CONFIRMADO** | chave de bairro era normalizada, mas display podia continuar com texto bruto como `TAPANA (ICOARACI)`, incompatível com `TAPANA` do GeoJSON | aliases contextuais + display canônico baseado na chave normalizada | teste geo para alias; **não executado aqui** |
| BUG-005 — Registrar bug cobre paginação | **CONFIRMADO visualmente** | FAB fixo ocupava área de interação inferior | ação movida para header e CSS deixou de usar sobreposição flutuante | QA visual pendente em browser real |
| BUG-006 — `30 dias` cai em período errado | **CONFIRMADO por leitura de código** | parser não possuía caminho explícito consolidado para rolling 30d | `parse_period` agora suporta today/yesterday/week/7d/30d/60d/90d/year/custom | teste adicionado; **não executado aqui** |
| BUG-007 — filtro sem evidência | **CONFIRMADO por leitura de query** | filtro não representava corretamente o complemento dos comprovantes com evidência | conjunto de IDs com evidência é calculado e `yes/no` são complementares | teste adicionado; **não executado aqui** |
| BUG-008 — KPI histórico usa status atual | **CONFIRMADO por revisão temporal** | comprovantes e entregas podiam ser lidos pelo estado atual em consultas antigas | reconstrução `as_of=end`: retido até o corte e não recuperado antes/dele | testes históricos adicionados; **não executados aqui** |
| BUG-009 — destaque “maior taxa” usava valor | **CONFIRMADO** | highlight de retenção escolhia `retained_value`, mas exibia `retention_rate` | seleção corrigida para `retention_rate` | coberto por revisão estática; teste Django recomendado |

## Estados de execução SSW
A v0.5.0.0 diferencia os relógios de:
- despacho;
- execução do robô;
- importação;
- heartbeat.

Códigos previstos na reconciliação: `ROBOT_DISPATCH_TIMEOUT`, `WORKER_PROCESS_LOST`, `WORKER_HEARTBEAT_LOST`, `ORPHAN_RUNNING_JOB`.

## Regra de fechamento de retenção
Documentação antiga foi corrigida. O estado consolidado CTRC posterior `ENTREGUE` encerra a retenção ativa originada pelo SSW na data operacional correta. Isso **não** identifica automaticamente um motorista recuperador. Recuperação manual/validada permanece um fato separado e auditável.
