# Mapa Operacional — refinamento visual v0.4.0.2

Escopo estritamente visual/UX sobre a baseline funcional v0.4.0.1.

## Alterações

- paleta dark/low-profile mais contida;
- regiões sem movimento passam a ter menor contraste;
- labels são priorizados e usam `hideOverlap` para reduzir colisões;
- mapa principal recebe melhor ocupação visual, fundo cartográfico discreto e controles de leitura mais leves;
- tooltip passa a destacar a métrica selecionada e mantém os mesmos dados do payload existente;
- legenda dinâmica é renderizada externamente sem alterar o cálculo da métrica;
- breadcrumb é exibido somente no drill-down para bairros;
- ranking, alertas, resumo e detalhe usam a mesma informação já retornada pela API;
- estados loading/empty/error foram refinados;
- cache busting CSS/JS evita reaproveitamento do visual antigo pelo navegador.

## Garantias

- nenhum arquivo Python foi alterado;
- nenhuma migration foi criada/alterada;
- `apps/operations/geo.py`, views, modelos, importador e `robot_ssw` permanecem idênticos à v0.4.0.1;
- não houve mudança de regra de retenção, ocorrência 13, entrega limpa, temporalidade, filial ou normalização geográfica.

## Arquivos visuais alterados

- `static/css/app.css`
- `static/js/geo_map.js`
- `templates/base.html` (somente cache bust do CSS)
- `templates/operations/map.html` (somente cache bust do JS)
- `templates/operations/today.html` (somente cache bust do JS)
- `VERSION`
- `VERSION.txt`
