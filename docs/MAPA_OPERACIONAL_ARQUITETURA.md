# Arquitetura — Mapa Operacional V1

## Princípio

> A filial não define o mapa. As entregas definem o mapa.

A unidade configurada (`SSW_ROBOT_UNIT`) é um filtro/proveniência do deployment. A geometria exibida é determinada por UF, município e bairro encontrados nos movimentos operacionais do período.

## Pipeline

```text
Filtro (unidade + período + motorista + métrica)
        ↓
operational_movements_for_period()
        ↓
endereços já importados do SSW
        ↓
normalização geográfica conservadora
        ↓
fatos por tentativa (ROM)
        ↓
agregação por município/bairro
        ↓
API JSON enxuta
        ↓
GeoJSON carregado separadamente
        ↓
ECharts registra geometria e pinta somente regiões com operação
```

## Data operacional

O módulo reutiliza `operational_movements_for_period()`. Quando existe ocorrência 85 `SAIDA PARA ENTREGA`, ela prevalece sobre a data de emissão do romaneio. Data de importação não entra em agregação histórica.

## ROM x CTRC

A estatística histórica da tentativa usa ocorrências `SSW_ROMANEIO` vinculadas ao `DeliveryMovement`.

- ROM 1 / ENTREGUE → tentativa entregue.
- ROM 34 → retenção ocorrida naquela tentativa/região.
- ROM 13 → tentativa prejudicada pelo horário.

O estado atual de comprovantes não é inferido novamente pelo mapa; `RetainedProof.status` continua sendo a fonte para comprovantes atualmente ativos. Assim ROM 34 histórico não volta a significar automaticamente “retido hoje”.

## Entrega limpa — definição V1

Na V1 uma tentativa é considerada limpa quando:

1. a ocorrência ROM daquela tentativa indica entrega;
2. a tentativa não possui ROM 34;
3. a tentativa não possui ROM 13;
4. o CT-e possui uma única tentativa conhecida na base.

Outros códigos negativos não são classificados automaticamente até homologação operacional. Essa limitação evita inventar regra de negócio.

## Normalização

Normaliza acentos, caixa, espaços e pontuação. Não há fuzzy matching automático.

Aliases são contextualizados por:

`UF + município + texto recebido`.

“CENTRO” nunca é uma chave global.

## Seleção automática de nível

- município dominante >= `GEO_DOMINANT_CITY_THRESHOLD` e provider de bairros disponível → bairros;
- caso contrário → municípios.

O threshold padrão é 80% e pode ser alterado por ambiente.

## Outliers

Quando uma região concentra pelo menos 70% das tentativas, regiões municipais abaixo de 2% da massa podem ser removidas apenas do enquadramento visual e informadas como “fora da área principal”. Elas continuam no resumo/ranking e não são apagadas dos dados.

## Performance

- nenhuma lista de CT-es é enviada ao browser para pintar o mapa;
- geometria e métricas são separadas;
- GeoJSON é cacheado pelo navegador durante a sessão;
- payload agrega por região;
- Django LocMemCache mantém o resumo por 60s;
- somente movimentos do período são carregados.

## Multi-filial

Não existe condição de UI/backend `if branch == BEL` ou `if branch == CWB`.

Limitação da baseline 0.3.0.10: movimentos não guardam `branch_code`. A V1 é multi-filial por **deployment/base ativa**; `SSW_ROBOT_UNIT=CWB` faz a mesma engine trabalhar como CWB. Consultar BEL e CWB misturados numa mesma base requer futura proveniência por movimento/importação.

O bridge externo ao robô foi ajustado para validar `.env SSW_UNIT` contra `SSW_ROBOT_UNIT`, removendo a validação antiga que exigia literalmente BEL. O diretório `robot_ssw/` permanece congelado.
