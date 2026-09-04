# Patch 0.2.2-p2 — Correção BUG-0001 / BUG-0002

## BUG-0001 — Carregamento da Importação
**Classificação ajustada:** P2 — função/feedback operacional incompleto.

Correções:
- barra de upload em tempo real;
- indicador animado enquanto Django processa o relatório;
- etapa atual consultada por polling;
- tempo decorrido e nome do arquivo;
- recarga automática somente após a conclusão.

## BUG-0002 — Disponíveis hoje + formatação dos números
**Classificação ajustada:** P1 na regra de rota; P3 apenas no polimento numérico.

Correções:
- rota com `SAIDA PARA ENTREGA` recente pode continuar ativa no dia seguinte/virada de fim de semana;
- cenário 29/08 → 31/08 coberto;
- ocorrência posterior antes do dia encerra o carry-over;
- entrega ocorrida durante o dia não remove a rota daquele dia;
- `Disponíveis hoje` não depende mais do período histórico selecionado;
- KPIs financeiros formatados em pt-BR e forma compacta.

## Reteste solicitado
1. importar a base;
2. abrir Importações SSW e observar o indicador durante todo o processamento;
3. abrir Dashboard em 31/08/2026;
4. confirmar rotas emitidas em 29/08 ainda em `SAIDA PARA ENTREGA`;
5. confirmar que os comprovantes compatíveis aparecem em `Disponíveis hoje`;
6. conferir formatação `R$ 3,02 mi` / `R$ 426,8 mil`.
