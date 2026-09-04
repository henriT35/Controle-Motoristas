# Performance — v0.9.2.0

## Objetivo

Evitar reconstruções históricas, N+1 e cálculo repetido do ranking/Portal em cada request.

## Instrumentação

Marcadores principais:

- `PERF dashboard.*`;
- `PERF ranking.*`;
- `PERF portal.*`;
- `PERF proofs.reconcile`;
- `PERF quality.events` quando aplicável.

## Estratégias existentes

- `select_related` / `prefetch_related`;
- agregações e consultas em lote;
- import engine v2 sem ORM no loop de linha;
- cache versionado;
- invalidação centralizada após importação, validação, recuperação, mudança de retenção e configuração;
- Redis na VPS, fallback local configurado para Windows;
- gráfico pesado do Dashboard carregado separadamente;
- paginação em centrais administrativas.

## v0.9.2.0

A avaliação passou a persistir eventos ROM13, oportunidades apresentadas, obrigações de ressalva e snapshots de score. Isso evita depender de reconstrução heurística a cada abertura do Portal e fornece auditabilidade.

A importação v2 mantém proteção contra snapshot fora de ordem sem inserir queries por linha no hot path.

## Benchmark

Não prometer tempo exato sem medir no banco real. Medir cache frio/quente em Dashboard, Operação, Ranking, Portal, Motoristas e Retidos no ambiente de homologação/produção.

## Estabilização de navegação — 03/09/2026

A homologação local mostrou trocas de tela acima de 10 s. A causa principal não era o Waitress/Cloudflare, e sim trabalho de domínio sendo executado durante GETs e cache local isolado por processo.

Alterações aplicadas nesta rodada:

- Windows/SQLite passou de `LocMemCache` para `FileBasedCache` compartilhado em `local_data/cache`, permitindo que Waitress, scheduler e comandos de manutenção reutilizem a mesma fotografia;
- Redis permanece o backend da VPS/PostgreSQL;
- reconstrução canônica de evidências operacionais é cacheada uma única vez por versão de cache;
- Dashboard e Central de Comprovantes não executam mais `refresh_today_opportunities()` durante GET;
- Central de Avaliações não executa mais `sync_quality_events_for_movements()` durante GET;
- matching de oportunidades da Operação filtra comprovantes candidatos no banco por cliente/CNPJ/região antes do cálculo em Python;
- Operação do Dia solicita evidência apenas para a data aberta;
- pós-importação/startup pré-aquece métricas do mês atual, período anterior, KPIs e oportunidades de hoje;
- `ScreenPerformanceMiddleware` registra tempo total e, no Windows/SQLite, quantidade/tempo SQL das telas críticas;
- `PERFORMANCE_DIAGNOSTICO.bat` resume as requests mais lentas a partir de `local_data/logs/painel.log`.

Princípio adotado: **quando os dados mudarem, calcule; quando o usuário abrir uma tela, apenas consulte**.

A Nota V3 também usa **01/09/2026 como início efetivo da amostra**: ao consultar período anual, estatísticas operacionais podem cobrir o ano inteiro, mas tentativas anteriores ao rollout não diluem a taxa de Qualidade nem a elegibilidade do ranking.

## R2 — diagnóstico real e snapshots persistentes

Medição real recebida em 03/09/2026:

- Dashboard frio: **17,150 s**;
- SQL do mesmo request: **0,420 s**;
- Ranking: **16,166 s**;
- `ranking.movements`: **9,630 s**;
- `ranking.events`: **6,489 s**;
- Dashboard quente após cache: **0,118 s**.

Conclusão: o banco não era o gargalo principal. A diferença entre frio e quente provou que o custo estava na reconstrução Python do Ranking.

A R2 mantém o cálculo pesado fora da navegação e acrescenta uma segunda camada persistente: `DriverScoreSnapshot` guarda a fotografia completa de cada motorista/período. Quando o cache é invalidado, Dashboard/Ranking reidratam `DriverMetric` do snapshot e registram `PERF ranking.snapshot_hit`, em vez de reprocessar milhares de `DeliveryMovement`.

O snapshot atual é refeito no startup, pós-importação e decisões que alteram nota. Um lock compartilhado (`cache.add`) impede dois processos de reconstruírem simultaneamente o mesmo período.

Também foi corrigida a Regularidade de Retirada Exata: a unidade de cobrança é a parada do dia (`motorista + cliente + data`), não cada comprovante. O sistema materializa essas oportunidades pela rota independentemente de o motorista abrir o Portal.

**Homologação pendente:** medir novamente no Windows real. O resultado esperado no próximo diagnóstico é que, após invalidação do cache, apareça `ranking.snapshot_hit` e o Dashboard não volte a executar `ranking.movements`/`ranking.events` de vários segundos durante a request. Não registrar tempo como PASS antes dessa medição.

## R3 — período padrão, gráfico pré-aquecido e diagnóstico limpo

A R2 comprovou no Windows que o Ranking preparado cai para ~0,01 s por cache/snapshot e que o cálculo de preparação caiu para ~0,5 s. A R3 remove fontes de ruído e dois gargalos secundários.

- `warm_navigation_cache()` agora resolve a mesma janela definida em `SystemSettings.period_default`; antes sempre aquecia o mês atual, mesmo se o usuário tivesse configurado 30d/90d/ano.
- `_evolution_payload()` do Dashboard é pré-aquecido fora do GET. O gráfico continua assíncrono/lazy, mas a primeira chamada passa a ler o payload preparado.
- Entregas Gerais carrega `cte__retained_proof` no `select_related`, evitando uma consulta por linha da tabela, e não executa duas vezes a mesma busca de CT-es entregues.
- o executor escreve `PERF session.start` somente após sincronização/warmup. O diagnóstico usa esse marcador e não mistura tempos antigos de outras builds/sessões.
- o relatório mostra `Ultima`, `Media` e `Max` por tela dentro da sessão atual.

Meta de homologação: medir novamente no Windows depois da R3. A lista principal do diagnóstico deve refletir apenas a navegação feita após o startup atual.
