# QA — Estabilização de Navegação v0.9.2.0

Data: 03/09/2026

## Escopo implementado

- cache local Windows compartilhado entre processos (`FileBasedCache`);
- cache da reconstrução temporal canônica;
- remoção de sincronizações pesadas dos GETs de Dashboard, Comprovantes e Avaliações;
- pré-aquecimento após startup/importação;
- filtro de candidatos de oportunidade antes do matching em Python;
- Operação do Dia limitada à evidência da data aberta;
- marco oficial da Avaliação V3 em 01/09/2026, inclusive no denominador da amostra/Qualidade;
- Central ROM13 com modal responsivo;
- instrumentação de request + SQL e diagnóstico local.

## QA executado neste ambiente

PASS:

- `python -m compileall` em apps/config/manage.py;
- `node --check static/js/app.js`;
- `scripts/qa/test_navigation_performance_v092_static.py`;
- `scripts/qa/test_migrations_v092_static.py`;
- `scripts/qa/test_template_routes_static.py`;
- `scripts/qa/test_v092_contract_static.py`;
- regressão real de retenção com 12 relatórios / 27.126 linhas;
- BNU046259-4 resolvido pelo CTRC entregue;
- CWB055520-7 resolvido pelo CTRC entregue;
- `robot_ssw/` comparado byte a byte com a baseline de origem: 17/17 idênticos.

## O que precisa ser medido no Windows real

Esta rodada altera o caminho de performance; os tempos finais não foram inventados neste ambiente.
Depois de iniciar o projeto, navegar por Dashboard, Operação, Motoristas, Retidos e Avaliações e executar:

`PERFORMANCE_DIAGNOSTICO.bat`

O relatório usa `local_data/logs/painel.log` e mostra requests lentas e quantidade/tempo SQL.

## Homologação externa pendente

- `python manage.py check`;
- `python manage.py makemigrations --check --dry-run`;
- aplicação da migration `core.0004_v0_9_2_0_evaluation_start_date`;
- smoke test HTTP real no Waitress;
- medição cache frio/quente no banco real;
- validação visual do modal em 1366x768 / 1280x720 / mobile;
- PostgreSQL/Redis/VPS.
