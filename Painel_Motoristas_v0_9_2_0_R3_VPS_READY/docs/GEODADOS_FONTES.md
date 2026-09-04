# Fontes geográficas — Mapa Operacional V1

## Municípios do Brasil

**Fonte primária:** IBGE — API de Malhas Geográficas v3.

- Documentação: https://servicodados.ibge.gov.br/api/docs/malhas?versao=3
- Formato utilizado: `application/vnd.geo+json`.
- Qualidade: `minima`, própria para aplicações web.
- Para a visão municipal a V1 solicita a malha simplificada da UF com subdivisão em municípios.

A própria documentação do IBGE informa que as malhas simplificadas são voltadas para aplicações web, evitando o custo das malhas cartográficas originais.

## Bairros de Belém/PA

A V1 homologa o nível de bairros de Belém usando o arquivo público:

https://raw.githubusercontent.com/samuel-c-santos/geovisor-belem/refs/heads/master/data/bairros.geojson

Repositório:

https://github.com/samuel-c-santos/geovisor-belem

O repositório publica uma camada GeoJSON de bairros de Belém e documenta como referências cartográficas:

- IBGE — Base de Faces de Logradouros do Brasil (2023);
- CODEM — Mapas dos bairros de Belém (2022);
- SNIRH/ANA para referências complementares.

O projeto do provider está sob licença MIT. O Painel não copia/edita manualmente os polígonos; consome a camada publicada e normaliza somente o nome usado para cruzamento com o SSW.

## Regra de proveniência

Providers de bairro são cadastrados por **UF + município**, nunca por filial.

Isso significa:

- BEL não chama um `mapa_belem()` especial;
- a mesma filial pode entregar em outro município e o mapa passa ao nível municipal;
- CWB usa a mesma engine e a malha municipal oficial do IBGE;
- um nível de bairro para Curitiba poderá ser habilitado adicionando uma fonte confiável de Curitiba ao registro de providers, sem mudar a lógica do motor.

## Dependência de rede e fallback

Os indicadores do mapa são calculados no backend a partir do banco local e **não dependem da internet**.

A geometria é carregada separadamente no navegador. Se a fonte geográfica estiver temporariamente indisponível:

- os dados operacionais continuam calculados;
- ranking/resumo continuam disponíveis;
- a área do mapa informa indisponibilidade da geometria em vez de inventar um desenho.

A V1 não usa Google Maps, API paga ou geocodificação por documento.
