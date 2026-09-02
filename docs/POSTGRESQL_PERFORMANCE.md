# PostgreSQL Performance

PostgreSQL continua sendo o banco oficial de produção. SQLite permanece apenas como modo local rápido.

## Índices adicionados/revisados

### DeliveryOccurrence
- `(code, occurred_at)` — já existente;
- `(cte, occurred_at)` — status cronológico de CT-e;
- `(movement, occurred_at)` — status cronológico do movimento.

### RetainedProof
- `(status, retained_at)` — críticos/abertos por idade;
- `(client, status)` — pendências por cliente;
- `(original_driver, retained_at)` — indicadores do motorista original.

### ImportRun
- `(status, created_at)` — filas/histórico;
- `(kind, start_date, end_date)` — reconciliações e períodos.

### GeneratedReport
- `(report_type, start_date, end_date, format)` — histórico/cache futuro de relatório.

## Regras
- não foram adicionados índices aleatórios em todas as colunas;
- `Decimal` foi preservado para valores financeiros;
- bulk size inicial = 1.000, devendo ser benchmarkado no servidor PostgreSQL real;
- otimizações não dependem de comportamento exclusivo do SQLite.

## Produção
Manter `CONN_MAX_AGE=60` conforme configuração atual e medir as queries críticas com `EXPLAIN ANALYZE` após existir volume real no PostgreSQL.
