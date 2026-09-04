# Mapa Operacional — análise inicial

## Baseline auditada

- Versão encontrada em `VERSION.txt`: **0.3.0.10**.
- Stack: Django/Python, templates server-rendered, JavaScript/CSS próprios e Apache ECharts já utilizado em outras telas.
- Apps relevantes: `operations`, `clients`, `drivers`, `proofs`, `ssw`, `dashboard`, `reports`, `core`.
- O core homologado `robot_ssw/` é tratado como componente congelado e não será alterado.

## Onde o módulo será integrado

1. `Operação de Hoje`: card compacto de cobertura geográfica alimentado pelos movimentos reais da data operacional.
2. Nova tela `Mapa Operacional`: análise por período, métrica e região, com ranking e alertas.
3. Backend: serviço geográfico em `apps/operations/geo.py` e endpoints JSON em `apps/operations/views.py`.
4. Frontend: `static/js/geo_map.js` e estilos específicos adicionados ao tema atual.

## Dados geográficos já existentes

O importador SSW 036 já persiste em `ClientAddress`:

- `street` ← `LOCAL DE ENTREGA`;
- `district` ← `BAIRRO`;
- `postal_code` ← `CEP ENTREGA`;
- `city` / `state` ← `CIDADE_ENTREGA`;
- `normalized_address` para identidade do endereço.

`DeliveryMovement` associa o endereço a CT-e, romaneio, motorista, cliente, peso, volumes e tentativa.
`DeliveryOccurrence` preserva código, descrição, data/hora e vínculo com a tentativa.

## Dados/limitações encontrados

### Filial

A baseline não possui `branch_code` nos movimentos/romaneios nem proveniência da unidade em cada entidade operacional. A unidade SSW atual é uma configuração do deployment (`SSW_ROBOT_UNIT`). Portanto, a V1 será **multi-filial por deployment/unidade ativa**, sem hardcode de BEL; a mesma engine funciona quando `SSW_ROBOT_UNIT=CWB`. Misturar BEL e CWB na mesma base e filtrar historicamente por filial exige uma futura migração de proveniência por importação/movimento.

O bridge atual possui uma validação antiga que exige literalmente `BEL` no `.env`; será corrigido para comparar com `SSW_ROBOT_UNIT`, sem alterar o core homologado.

### Geometria

- Municípios: API oficial de Malhas do IBGE, em GeoJSON simplificado para web.
- Bairros de Belém: provider de GeoJSON público baseado em divisão real de bairros, documentado em `GEODADOS_FONTES.md`.
- A engine não será condicionada à filial; providers de bairro são associados a **município/UF** conforme disponibilidade de geodados.
- Quando não houver malha de bairros, a engine permanece funcional em nível municipal.

## Regras temporais

A baseline já possui `operational_movements_for_period()` e usa ocorrência 85 `SAIDA PARA ENTREGA` como fonte principal de data operacional. O mapa deve reutilizar essa lógica e nunca usar data de importação.

## ROM × CTRC

A V1 geográfica não reinterpreta o estado atual do comprovante. Para fatos históricos da tentativa, ocorrências vinculadas ao movimento são usadas; para comprovantes atualmente ativos, `RetainedProof.status` é a fonte operacional. Assim não se reintroduz o bug antigo de tratar qualquer ROM=34 como retenção atual.

## Modelos afetados

Nenhum novo modelo é necessário na V1. Isso evita introduzir migrations arriscadas numa baseline cujos apps locais hoje são sincronizados sem migrations versionadas. O módulo usa os modelos existentes e uma camada de serviço/cache.

## Arquivos previstos

- `apps/operations/geo.py` — normalização, agregação, métricas e configuração de geodados.
- `apps/operations/views.py` — página e endpoints JSON.
- `apps/operations/urls.py` — novas rotas.
- `templates/operations/today.html` — mapa compacto.
- `templates/operations/map.html` — mapa analítico.
- `static/js/geo_map.js` — engine visual ECharts e carregamento progressivo.
- `static/css/app.css` — acabamento low-profile.
- `apps/operations/tests_geo.py` — regressão da lógica geográfica.
- `apps/ssw/robot_bridge.py` — remover hardcode BEL da validação externa ao core.
- documentação e verificador de build.

## Riscos de regressão e mitigação

- **Relatórios zerados/consultas inconsistentes:** o mapa não reutilizará KPIs de relatórios; agregará a partir de `operational_movements_for_period` e testará resultados contra fixtures.
- **N+1:** carregar movimentos/endereços/CT-es em consultas seletivas e agregar em memória somente os movimentos do período solicitado.
- **Geodados externos indisponíveis:** UI apresenta fallback de lista/ranking e estado de indisponibilidade; os KPIs não dependem da geometria para serem calculados.
- **Bairro escrito de formas diferentes:** normalização determinística e aliases conservadores; nenhum fuzzy matching automático perigoso.
- **Mapas pesados:** geometria e métricas separados, malha simplificada, cache browser-side e nenhum CT-e individual enviado ao frontend.
