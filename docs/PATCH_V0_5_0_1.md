# Patch v0.5.0.1 — Correções do levantamento operacional

## Base obrigatória

Aplicar somente sobre **Painel Motoristas v0.5.0.0**.

## O que este patch corrige

- Ranking de motoristas passa a considerar a confiabilidade da amostra. Motoristas abaixo do mínimo continuam consultáveis, mas ficam atrás dos elegíveis no ranking principal.
- Adiciona marcação explícita **Teste/Homologação** em motorista. Esses registros são excluídos de KPIs, médias, ranking, mapa, clientes e relatórios oficiais.
- O card **Desempenho médio** passa a calcular a média dos motoristas com atividade, mantendo separadamente a informação de quantos estão elegíveis para o ranking.
- Links de ordenação/filtros da tela de motoristas preservam o período atual.
- O filtro global diferencia **Mês atual** de **Últimos 30 dias**.
- O gráfico de evolução do Dashboard abre a Operação do Dia ao clicar tanto na bolinha da série quanto diretamente na data do eixo.
- A Operação do Dia inclui o fallback legado já usado pelo motor geográfico para romaneios sem ocorrência 85 capturada e permite navegar para uma rota já preparada em data futura existente na base.
- Clientes: o campo **Bairro** é atualizado de acordo com a **Cidade** selecionada.
- Mapa: regiões ativas recebem maior prioridade de label. Para municípios sem uma malha pública/homologada de bairros, o clique abre um detalhamento das regiões/bairros encontrados no SSW em vez de deixar a interação sem resposta.
- Terminologia de operação simplificada: **Retenção**, **Horário**, **Tentativas**, **Entregas** e **Entrega limpa**.

## Importante sobre a contagem de tentativas

Este patch **não inventa nem multiplica tentativas**. A regra continua sendo uma tentativa por `DeliveryMovement` (CT-e + romaneio). A suspeita de subcontagem deve ser validada contra a base real. As correções desta versão eliminam duas distorções confirmadas de leitura: períodos que eram perdidos ao ordenar/abrir telas e o ranking que tratava amostras pequenas como equivalentes às grandes.

## Atualização do banco

Foi adicionado `Driver.is_test`.

A distribuição local já executa `makemigrations` e `migrate` no início. Portanto:

1. feche o Painel;
2. copie o patch preservando as pastas;
3. abra pelo `EXECUTAR_LOCAL.bat`;
4. aguarde a etapa de migrations terminar;
5. entre no perfil do motorista fictício e use **Marcar como teste** uma única vez.

Não há exclusão automática por nome, CPF ou heurística.

## Checklist rápido de homologação

1. **Dashboard** — selecionar 7 dias e clicar em uma data do eixo (ex.: 26/08). Deve abrir a Operação do Dia correspondente.
2. **Motoristas** — selecionar Últimos 30 dias, ordenar por desempenho e confirmar que o período não muda. Linhas com amostra baixa devem aparecer identificadas e não ultrapassar motoristas elegíveis no ranking principal.
3. **Motorista fictício** — marcar como teste e confirmar que desaparece dos indicadores oficiais, permanecendo acessível no filtro Teste/Homologação.
4. **Operação do Dia** — navegar para um dia anterior e para uma rota preparada disponível na próxima data. Comparar os cards com a cobertura/mapa.
5. **Clientes** — selecionar Belém e conferir que o seletor de Bairro passa a listar somente bairros encontrados para Belém no período.
6. **Mapa** — clicar Belém e outro município. Belém mantém polígonos de bairros; município sem malha homologada deve mostrar o detalhamento regional SSW, não uma tela vazia.

## Limitação conhecida do mapa

A v0.5.0.1 **não fabrica polígonos de bairros** para Ananindeua, Marituba, Benevides ou outros municípios que ainda não possuem fonte geográfica de bairros homologada no projeto. Nesses casos o sistema apresenta os bairros/regiões operacionais encontrados nos dados SSW e suas métricas. Quando uma fonte confiável for homologada, essa mesma navegação poderá renderizar os polígonos.

## Testes feitos neste ambiente

- compilação de todos os módulos Python;
- `node --check` em `static/js/app.js`;
- `node --check` em `static/js/geo_map.js`;
- comparação do core `robot_ssw` com a baseline;
- teste de integridade do ZIP/overlay.

A suíte Django depende da `.venv`/Django e do banco da instalação real, portanto deve ser executada no ambiente de homologação após a atualização.
