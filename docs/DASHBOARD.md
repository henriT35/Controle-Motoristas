# Dashboard — evolução operacional

## Período
Usa o parser global de períodos. `30d` significa janela móvel de 30 dias incluindo a data final, não “mês atual”.

## Evolução
Domingo sem atividade é omitido visualmente. Domingo com qualquer atividade real continua presente.

## Interação
Clique em ponto do gráfico segue o princípio `Resumo → Clique → Detalhe` e abre a Operação do Dia com data/foco.

## KPIs históricos
Comprovantes pendentes são reconstruídos no fim do período (`as_of=end`), evitando que uma recuperação ocorrida depois apague retroativamente uma pendência que existia no corte.

## Escopo
O Dashboard resume a coorte operacional do período. Análise completa de comprovantes e clientes continua nas telas/relatórios específicos.

## v0.7.0.0 — reconciliação com a Operação do Dia

O Dashboard consome a mesma fonte temporal canônica da Operação. O ponto diário do gráfico não pode receber um romaneio só porque o CT-e teve uma atualização posterior.

A série de **Entregas** é atribuída à data operacional da tentativa/romaneio e só considera o CT-e concluído se existir ocorrência ENTREGUE datada até o fechamento daquele dia. Uma entrega posterior não migra a rota para o dia da entrega.

A série de **Retenções/Pendências** usa a origem ROM34/rota canônica. Estoque atual, importação ou atualização posterior não reescrevem o histórico. O critério de reconciliação é: card/ponto do Dashboard deve ser explicável pela Operação do Dia aberta pelo clique.

