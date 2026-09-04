# Testes — Mapa Operacional V1

## Casos automatizados adicionados

Arquivo: `apps/operations/tests_geo.py`.

Cobre:

- normalização de acentos/caixa/espaços;
- alias de bairro contextualizado por município;
- ROM 1 como entrega da tentativa;
- ROM 34 como retenção histórica;
- ROM 13 como prejudicada pelo horário;
- comprovante ativo separado do fato histórico;
- seleção automática de bairros em Belém quando há provider;
- CWB usando a mesma engine sem hardcode de BEL;
- rejeição segura de consulta cruzada de filial numa base V1 sem proveniência por movimento.

## Validações estáticas executadas na geração

- `py_compile` em todos os arquivos Python do pacote;
- `node --check` em `static/js/geo_map.js` quando Node está disponível;
- comparação SHA-256 de todo o diretório `robot_ssw/` antes/depois;
- inspeção do ZIP final.

## Limitação do ambiente de construção

O ambiente utilizado para gerar o pacote não possui Django instalado e não possui acesso de rede para instalar dependências via pip. Por isso `manage.py check` e a suíte Django não podem ser executados aqui.

O pacote inclui `VERIFICAR_BUILD_MAPA.bat`, que executa essas verificações no ambiente Windows do projeto depois de preparar a `.venv`. O release não deve ser considerado homologado em produção até esse BAT e o teste real da interface passarem na máquina da aplicação.

## QA manual recomendado

1. importar um período BEL com dados reais;
2. abrir Operação de Hoje e comparar entregas do mapa com movimentos da data;
3. abrir Mapa Operacional e alternar métricas;
4. clicar Belém e validar bairros;
5. conferir Pedreira/Marco/etc. com dados do SSW;
6. testar ocorrência 34 e 13 conhecidas;
7. configurar uma instalação de teste com `SSW_ROBOT_UNIT=CWB` e confirmar visão municipal PR;
8. desligar internet e confirmar que ranking/resumo permanecem enquanto a geometria informa indisponibilidade.

## Regressão 0.4.0.1 — malha IBGE com `codarea`

Caso real observado: métricas/ranking municipais carregavam, mas o mapa exibia “A fonte geográfica respondeu sem polígonos utilizáveis”.
A malha GeoJSON do IBGE pode trazer `properties.codarea` sem nome do município. A V1 original descartava essas feições.

Correção: resolver `codarea` pela API oficial de Localidades do IBGE por UF e cachear o cadastro durante a sessão.
