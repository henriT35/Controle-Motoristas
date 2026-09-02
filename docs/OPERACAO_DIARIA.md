# Operação do Dia — histórico operacional

## Objetivo
A tela não deve apagar a operação quando os romaneios deixam de estar ativos. A mesma visão de `/operacao/hoje/` aceita uma data histórica por `?date=AAAA-MM-DD` e reconstrói a fotografia daquele corte.

## Regras
- Data operacional da rota prefere ocorrência 85 `SAIDA PARA ENTREGA`.
- Entrega é considerada concluída no histórico somente se a ocorrência de conclusão já existia até a data consultada.
- Comprovante é considerado aberto no corte se `retained_at <= corte` e `recovered_at` é nulo ou posterior ao corte.
- O dia atual continua acionável; dias antigos são consulta histórica.
- Navegação anterior/próximo dia preserva o foco recebido do Dashboard.

## Drill-down do Dashboard
Exemplos:
- `/operacao/hoje/?date=2026-08-04&focus=deliveries`
- `/operacao/hoje/?date=2026-08-18&focus=retentions`
- `/operacao/hoje/?date=2026-08-20&focus=proofs`

## Domingo
Domingo sem atividade operacional real é omitido do gráfico de evolução, sem excluir dados do banco. Se houver tentativa/rota/entrega/retenção/ocorrência no domingo, a data permanece no gráfico.

## Limitação conhecida
Um fato cancelado sem timestamp histórico próprio não pode ser reconstruído retroativamente com precisão apenas pelo status atual. Se esse caso se tornar relevante para análise histórica, criar evento/auditoria temporal explícita em release futura.

## v0.7.0.0 — temporalidade canônica e retenções do dia

A Operação do Dia passou a usar uma única evidência canônica por romaneio. A primeira ocorrência **85 / SAIDA PARA ENTREGA** datada confirma a data. Quando não existe 85 datada, o primeiro fato `SSW_ROMANEIO` datado pode inferir a operação. Sem fato datado, o romaneio permanece em planejamento/data não confirmada.

Um evento ROM posterior não cria uma nova data para o mesmo romaneio. CTRC consolidado, emissão, `movement_date` e data de importação não materializam a data da rota. Carry-over é permitido somente no dia atual.

A tela ganhou o KPI **Retidos no dia**, cuja unidade é a retenção originada operacionalmente naquela data. Recuperações posteriores não apagam a retenção histórica.

O CT-e listado em Detalhes da Rota é clicável e abre uma ficha completa, preservando a URL de retorno.


## v0.7.0.1 — confirmação ao vivo do dia corrente

A fonte histórica continua sendo ROMANEIO datado. Porém a Operação de Hoje também é uma fotografia operacional ao vivo. Se o estado consolidado **atual** do CT-e for `SAIDA PARA ENTREGA`, o romaneio entra no dia corrente como `CONFIRMED`, mesmo que a trilha ROMANEIO não possua data suficiente naquele snapshot.

Essa regra tem escopo estritamente atual:

- vale somente quando `target_date == timezone.localdate()`;
- não altera histórico encerrado;
- não muda a data canônica do romaneio;
- não usa CTRC para materializar uma rota em 01/09, 31/08 etc.;
- remove a rota de Planejamento apenas enquanto ela está operacionalmente observada como saída no dia atual.
