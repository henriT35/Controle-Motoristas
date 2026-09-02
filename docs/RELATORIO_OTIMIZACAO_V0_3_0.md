# Relatório de Otimização — Painel Motoristas v0.3.0

## Escopo
Rodada horizontal de performance cobrindo importador, ORM, views críticas, histórico, relatórios, frontend, startup Windows, logging e preparação PostgreSQL. O core homologado do Robô SSW foi congelado.

## Mudanças principais
1. Import Engine v2 em lote com preload, comparação em memória e bulk operations.
2. Timings persistidos em `ImportRun`.
3. Operação de Hoje elimina consulta de comprovantes por romaneio e reutiliza movimentos pré-carregados.
4. Perfil do Motorista elimina 12 consultas mensais independentes.
5. Clientes elimina N+1 de comprovantes recuperados.
6. KPIs de comprovantes consolidados em aggregate.
7. Histórico SSW usa AVG de duração no banco.
8. Configurações singleton e última sincronização recebem cache local curto.
9. Caderno de Bugs paginado em 50 registros.
10. ECharts usa registry de resize e debounce central.
11. Startup Windows executa `makemigrations` apenas quando o hash de `models.py` muda.
12. Logging recebe rotação 5 MB × 5 arquivos.
13. Índices compostos direcionados às consultas críticas.
14. Healthcheck e benchmarks integrados ao projeto.

## Segurança e regras
Nenhuma proteção foi removida. CSRF, autenticação e permissões permanecem. Valores financeiros continuam Decimal. Histórico não é recriado. Recuperações manuais não são sobrescritas.

## Robô SSW
Os seis arquivos do core homologado continuam com os mesmos SHA-256 do manifesto. Nenhum seletor Playwright foi alterado.

## Medições
A única medição runtime disponível no ambiente de construção sem Django foi o workload CPU de normalização: ganho médio de 71,80%. Tempos e queries web/importação completa devem ser medidos pelo comando incluído na máquina Windows real; valores não foram inventados.

## Risco controlado
O importador legado permanece temporariamente acessível via `SSW_IMPORT_ENGINE=v1`. O padrão é v2. Após homologação real e comparação do golden dataset, o legado poderá ser removido em versão futura.
