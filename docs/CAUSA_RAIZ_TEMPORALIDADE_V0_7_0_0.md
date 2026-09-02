# Causa raiz — Temporalidade dos romaneios — v0.7.0.0

## Sintoma

Romaneios emitidos muitos dias antes apareciam em uma data operacional recente como “Data inferida”. Isso contaminava Operação do Dia e agregados do Dashboard.

## Causas encontradas

1. `inferred_manifest_ids` tratava **qualquer** ocorrência `SSW_ROMANEIO` datada dentro do período como prova de que o romaneio pertencia àquele dia. Assim, um evento posterior podia fazer o mesmo romaneio reaparecer em outra data.
2. O carry-over criado para a operação viva era aplicado também a consultas históricas.
3. `operational_movements_for_period` aceitava `movement_date` como fallback em cenários legados, permitindo que uma data não comprovada entrasse em KPIs.
4. A identidade de ocorrência ROM no importador não separava tentativa/movimento; CTRC consolidado ainda podia carregar vínculo de movimento legado.

## Correção

Cada romaneio passa a ter no máximo uma data canônica:

```text
85 ROM datado -> CONFIRMED
sem 85 + primeiro fato ROM datado -> INFERRED
sem fato ROM datado -> PLANNED / não confirmada
```

O primeiro fato é usado apenas quando não existe 85 datada. Fatos posteriores não criam novos dias. Carry-over somente hoje. CTRC consolidado, emissão, importação e `movement_date` não criam data operacional.

No importador, ROM é identificado por CT-e + semântica + movimento; CTRC é consolidado por CT-e e fica sem movimento. Um vínculo legado só é reparado automaticamente quando estava vazio; um fato já ligado a outra tentativa não é movido por hipótese.

## Impacto esperado

- romaneio antigo deixa de migrar para data recente;
- Dashboard e Operação reconciliam a mesma data;
- retenções usam origem de negócio, não importação;
- tentativas múltiplas do mesmo CT-e permanecem separadas.

## Limitação consciente

Sem fato ROM datado suficiente, o sistema prefere “data não confirmada”. Não existe fallback artificial D+1 nem janela arbitrária para esconder o problema.
