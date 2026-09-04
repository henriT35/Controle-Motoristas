# Bugs/riscos encontrados durante a implementação do Mapa V1

## ALTO — unidade do bridge hardcoded em BEL

**Confirmado.** `apps/ssw/robot_bridge.py` validava `.env SSW_UNIT` contra a string literal `BEL`, apesar do payload já usar `SSW_ROBOT_UNIT`.

**Impacto:** uma instalação CWB seria recusada no preflight antes do robô, mesmo que o core receba unidade dinamicamente.

**Correção V1:** comparar `.env SSW_UNIT` com `settings.SSW_ROBOT_UNIT`. O core `robot_ssw/` não foi modificado.

## ALTO — baseline sem proveniência de filial por movimento

**Confirmado.** `DeliveryMovement`, `Manifest` e `ImportRun` não registram a unidade/filial que originou cada linha operacional.

**Impacto:** uma única base contendo BEL e CWB não consegue separar historicamente os movimentos com segurança.

**Decisão V1:** não inventar filial. O motor aceita qualquer unidade como deployment ativo, mas rejeita consulta a outra unidade na mesma base. Uma V2 deve introduzir proveniência de unidade com estratégia de migração/reconciliação.

## CRÍTICO (pré-existente) — relatórios podem retornar zero com base populada

**Reportado pelo usuário; causa não tratada neste módulo.** O mapa não copia as consultas dos relatórios existentes. Seus números nascem diretamente da camada operacional e devem ser comparados em QA com os movimentos da base.

## MÉDIO — inconsistência de bairro no SSW

**Confirmado pelos dados reais.** Nomes de bairro podem conter complementos/variações. A V1 normaliza texto e permite aliases contextualizados, sem fuzzy matching automático.

## MÉDIO — geometria de bairro não existe de forma uniforme no Brasil

Municípios são cobertos pela API oficial do IBGE. Bairro depende de fonte municipal/pública confiável. Quando não houver provider, o sistema permanece no nível municipal.

## [CORRIGIDO 0.4.0.1] Malha municipal IBGE descartada por ausência de nome
- Severidade: ALTO
- Sintoma: KPIs, Top 5 e alertas carregados; mapa municipal vazio com mensagem de ausência de polígonos utilizáveis.
- Causa raiz: a malha GeoJSON do IBGE usa `properties.codarea` como identidade, enquanto o frontend exigia `nome`/`NM_MUN` para aceitar a feição.
- Correção: enriquecimento genérico `codarea -> nome` via API de Localidades do IBGE, cacheado por UF.
