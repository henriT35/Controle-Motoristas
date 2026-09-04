# QA Performance — v0.9.2.0 R3

Data: 03/09/2026

## Escopo

Rodada incremental sobre `Painel_Motoristas_v0_9_2_0_BASELINE_COMPLETA_OTIMIZADA_R2`.

## Alterações validadas estaticamente

- warmup respeita `SystemSettings.period_default`;
- gráfico Evolução Operacional é pré-aquecido fora da request;
- Entregas Gerais carrega `cte__retained_proof` junto com o CT-e;
- segunda consulta de `completed_cte_ids()` foi eliminada por interseção do conjunto já calculado;
- executores LOCAL/ONLINE escrevem marcador `PERF session.start` após sincronização/warmup;
- diagnóstico de performance separa sessão atual de histórico antigo;
- `robot_ssw/` permanece idêntico à R2.

## QA executado

- `python -m compileall`: PASS;
- suíte `scripts/qa/*.py`: PASS, exceto regressão de dados reais marcada SKIP porque `/mnt/data/qa_real_v092` não estava presente nesta execução;
- `test_navigation_performance_v092_r3_static.py`: PASS;
- comparação `robot_ssw`: 17/17 arquivos idênticos por SHA-256.

## Homologação externa pendente

Executar no Windows real:

1. iniciar `EXECUTAR_ONLINE.bat` ou `EXECUTAR_LOCAL.bat`;
2. navegar Dashboard → Ranking → Motoristas → Entregas Gerais → Dashboard;
3. executar `PERFORMANCE_DIAGNOSTICO.bat`;
4. confirmar que o TOP 20 é da sessão atual e que Entregas Gerais reduziu o número de queries;
5. confirmar que a primeira chamada do gráfico não retorna ao patamar ~2 s após o warmup.

Nenhum tempo runtime da R3 foi inventado neste ambiente.

## Fechamento do patch

- baseline R3: 544 arquivos;
- patch aplicado sobre cópia limpa da R2: 544 arquivos;
- diferenças de caminho após aplicação: 0;
- diferenças SHA-256/conteúdo: 0;
- integridade ZIP baseline: PASS;
- integridade ZIP patch: PASS.
