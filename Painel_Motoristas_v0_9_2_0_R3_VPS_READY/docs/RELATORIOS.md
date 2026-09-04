# Central de Relatórios — v0.5.0.0

## Regra de período
Index, preview, PDF e XLSX devem usar o mesmo período parseado e preservar a query do usuário. Rolling periods suportados incluem 7d/30d/60d/90d, além de semana, mês, ano e intervalo personalizado.

## Relatórios
1. Desempenho dos Motoristas.
2. Comprovantes Retidos.
3. Clientes.
4. Operação Diária.
5. SSW/importação.
6. Financeiro, limitado aos campos realmente presentes no banco.

## Não inventar finanças
O relatório financeiro só pode usar valores persistidos (por exemplo, frete/mercadoria/peso/status quando disponíveis). Não inferir pagamento, vencimento ou faturamento se esses fatos não existirem.

## Validação obrigatória em homologação
Para cada relatório, criar base conhecida e conferir Banco → Query → View → Arquivo. “Deixou de dar zero” não é prova suficiente.

## v0.7.0.0 — regra temporal compartilhada

Consultas e relatórios que trabalham por data operacional devem usar a mesma fonte canônica de romaneio da Operação do Dia. Não criar atalhos por emissão, importação ou CTRC consolidado. Quando não houver evidência suficiente, apresentar data não confirmada em vez de inventar um dia operacional.

