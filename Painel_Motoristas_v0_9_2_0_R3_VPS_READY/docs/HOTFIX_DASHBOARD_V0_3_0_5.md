# Hotfix v0.3.0.5 — Evolução Operacional

## Problema

O gráfico **Evolução Operacional** podia mostrar um pico artificial de `Pendências` no último dia do período. Isso acontecia porque toda movimentação ainda não concluída era classificada como pendência, inclusive rotas do dia ainda em andamento.

Além disso, o Import Engine v2 possuía um fallback `retained_at = now` para retenções sem `DATA OCORR`. Uma retenção histórica importada hoje podia, portanto, aparecer como se tivesse ocorrido hoje.

## Regra corrigida

- **Entregas:** CT-es concluídos, deduplicados por CT-e/dia operacional.
- **Retenções:** eventos documentais de retenção, preferindo código 34 / `MERCADORIA EM CONFERENCIA NO CLIENTE` com data real.
- **Pendências:** comprovantes retidos que continuam abertos, agrupados pela data em que a retenção nasceu.
- **Retenção sem data no SSW:** usa saída para entrega da rota; sem saída datada, usa D+1 da emissão. Nunca usa o instante da importação.
- **Eixo X:** `dd/mm`.

## Compatibilidade com dados já importados

O dashboard reconhece registros antigos cuja `retained_at` coincide com `created_at` (assinatura do fallback antigo) e tenta recuperar a data operacional histórica. Reimportar o relatório após o hotfix também corrige o `retained_at` no banco quando a nova data inferida é anterior.

## Escopo

O hotfix altera somente dashboard/importação. O diretório `robot_ssw/` e o fluxo Playwright homologado da opção 036 não são alterados.
