# Score Executivo

Objetivo: comparar execução e esforço sem transformar retenção operacional do cliente em falha automática do motorista.

Índice operacional = movimentações com entrega concluída ou conferência no cliente / movimentações.

Índice de esforço normalizado:
- 35% movimentações;
- 25% paradas;
- 20% romaneios;
- 20% peso.

Score final padrão: 60% operacional + 40% esforço.

Os pesos e a amostra mínima são persistentes em `SystemSettings`. Abaixo da amostra mínima o motorista aparece como `AMOSTRA BAIXA` e não entra no ranking principal.
