# QA PERFORMANCE / RETIRADAS EXATAS — v0.9.2 R2

Data: 03/09/2026

## Evidência real que motivou a rodada

Log Windows informado pelo usuário:
- dashboard.request: até 17,150 s;
- SQL: 0,420 s;
- ranking.total: 16,166 s;
- ranking.movements: 9,630 s;
- ranking.events: 6,489 s;
- dashboard quente: 0,118 s.

## QA executado neste ambiente

PASS:
- compileall Python;
- sintaxe Node `whatsapp_bridge/server.mjs`;
- QA portátil 6/6;
- migrations estáticas v0.9.1/v0.9.2;
- contrato de navegação/performance;
- novo contrato snapshot + histórico exato;
- contrato v0.9.1 e v0.9.2;
- fórmula V3;
- temporalidade;
- rotas/templates;
- Baileys;
- telefone BR;
- VPS estático;
- regressão real BNU046259-4/CWB055520-7 em 12 relatórios SSW / 27.126 linhas.

## O que foi alterado

- snapshot completo persistente para Ranking/Dashboard;
- snapshot fallback em cache miss;
- lock contra rebuild concorrente;
- remoção de `ImportRun` como invalidator global;
- ROM13 agregado no banco;
- Retirada Exata materializada pela rota independentemente do Portal;
- Regularidade agrupada por parada/dia;
- backfill desde 01/09/2026;
- CTRC `delivered_at` impede falsa obrigação histórica;
- Central/KPI contam omissões por parada.

## HOMOLOGAÇÃO EXTERNA PENDENTE

Este ambiente não possui Django runtime. No Windows real executar:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test
```

Depois iniciar o Painel, navegar Dashboard/Ranking pelo menos duas vezes, provocar uma invalidação (por exemplo após importação) e executar `PERFORMANCE_DIAGNOSTICO.bat`. Confirmar `ranking.snapshot_hit` e ausência de novo cálculo de 8–16 s dentro da request.
