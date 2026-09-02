# Mapa Operacional

## Objetivo

Transformar a geografia em uma dimensão operacional do Painel Motoristas usando os endereços reais já trazidos pelo relatório SSW 036.

## Tela Operação de Hoje

A lateral agora possui um mapa compacto “Cobertura Operacional”. Ele usa a data operacional selecionada e abre a análise completa pelo botão **Ver mapa**.

## Tela Mapa Operacional

Rota: `/operacao/mapa/` (dependendo do prefixo global configurado no projeto).

Filtros:

- unidade ativa;
- data inicial/final;
- métrica;
- motorista.

Métricas V1:

- Entregas;
- Retenções;
- Taxa de retenção;
- Prejudicadas pelo horário (ocorrência 13);
- Taxa por horário;
- Comprovantes retidos ativos;
- Entregas limpas;
- Taxa de entrega limpa;
- Peso;
- Clientes.

## Interação

- hover: mostra tentativas, entregas, retenções, ocorrência 13, comprovantes e sucesso;
- clique em município: tenta abrir bairros se houver provider homologado;
- clique em região: abre cartão de detalhamento;
- ranking e alertas usam exatamente o mesmo payload do mapa.

## Estado vazio

Se o período não tiver movimento localizado, a tela mostra estado vazio. Não são gerados dados fictícios.

## Localizações não resolvidas

Movimentos sem UF/cidade (ou sem bairro quando o nível é bairro) são contabilizados em `unresolved` e exibidos como qualidade de dados. Eles não desaparecem silenciosamente.

## Configuração

Variáveis opcionais:

```env
GEO_DOMINANT_CITY_THRESHOLD=0.80
GEO_ALERT_MIN_SAMPLE=10
GEO_OUTLIER_DOMINANCE_THRESHOLD=0.70
GEO_OUTLIER_MIN_SHARE=0.02
GEO_HOME_STATE=PA
GEO_HOME_CITY=Belem
```

`GEO_HOME_*` é apenas fallback de UX para instalações sem movimento; não limita território.


## Atualização v0.5.0.0
- Normalização contextual inclui variações reais de Tapanã/Icoaraci, entregando nome canônico compatível com a geometria.
- Clique municipal nunca deve ser silencioso: com malha de bairros ocorre drill-down; sem malha disponível é apresentado detalhe municipal/regional.
- Comprovantes ativos no mapa são reconstruídos no fim do período consultado, não pelo status atual indiscriminadamente.
- O design premium/low-profile da v0.4.0.3 foi preservado.
- A engine continua genérica e não deve conter `if filial == BEL` para geografia.
- Limitação V1 permanece: movimentos históricos ainda não carregam proveniência de filial suficiente para misturar várias filiais na mesma base com separação histórica perfeita.

## Atualização v0.6.0.0 — Município → bairros da rota
- Bairro é resolvido no contexto `UF + município + bairro`.
- O auto nível de bairro pode ser usado quando a operação real contém bairros, mesmo sem provider estático previamente cadastrado.
- Provider estático de Belém continua preferencial quando disponível.
- Para outros casos, resolvedor dinâmico tenta obter/cachear apenas os bairros presentes na operação.
- Bairro sem polígono não some: permanece como dado operacional/fallback textual e diagnóstico.

## v0.7.0.0 — fallback sem polígonos

Falha de geometria não é mais falha dos dados operacionais. Quando GeoJSON/provider não retornar polígonos utilizáveis, o mapa preserva KPIs, ranking e apresenta uma lista textual das regiões/bairros encontrados no SSW.

Estados esperados:
- **Completo:** polígonos e métricas.
- **Parcial:** regiões resolvidas no mapa e restantes preservadas nos dados/ranking.
- **Sem polígonos:** lista operacional por região/bairro; nenhum overlay deve bloquear a tela.

No drill-down de bairros, movimentos de outros municípios ficam fora do contexto selecionado e não são contados como “sem localização suficiente”. O indicador de insuficiência geográfica possui diagnóstico por motivo e amostra de registros.

