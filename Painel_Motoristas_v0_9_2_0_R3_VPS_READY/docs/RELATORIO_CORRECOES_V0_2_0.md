# Relatório de Correções — V0.2.0

## Correções aplicadas
- Design system dark executivo consolidado, sidebar ativa por página, header e login refeitos.
- Dashboard deixou de usar série de gráfico hardcoded e passou a usar dados agregados do banco.
- Corrigida a definição de entrega: `ENTREGUE` é obtido de `DeliveryOccurrence` do CT-e.
- Implementado Score Executivo configurável e regra de amostra mínima.
- Operação diária consolidada por romaneio, com match de comprovantes e aviso por bairro.
- Tela de Motoristas com filtros, paginação, score, execução e destaques.
- Perfil do motorista com KPIs e gráficos reais.
- Central de comprovantes com filtros, drawer e recuperação auditada.
- Clientes com indicadores e análise regional.
- Relatórios HTML, XLSX e PDF funcionais e registrados em `GeneratedReport`.
- Importações/histórico do SSW passaram a distinguir execução real de solicitação de robô pendente.
- Configurações persistentes em `SystemSettings`, protegidas por permissão server-side e auditadas.

## Dependência externa ainda pendente
- Robô Playwright no SSW real. Não foi simulado; requer acesso/credenciais e mapeamento das telas do SSW.

## Banco
- SQLite permanece como modo local rápido de homologação.
- PostgreSQL é o banco-alvo e está suportado via `.env.local` / `CONFIGURAR_POSTGRESQL_LOCAL.bat`.

## Validação no ambiente de geração
- Arquivos Python passam por compilação estática (`py_compile`).
- O parser do SSW foi preservado e validado contra o arquivo de agosto/2026.
- Testes Django runtime não puderam ser executados neste ambiente porque Django não está instalado e o ambiente não possui acesso à internet para instalar dependências. O `EXECUTAR_LOCAL.bat` faz essa instalação no Windows do usuário.


## Fechamento final do pacote
- Corrigida a propriedade `duration_seconds`, agora pertencente corretamente a `ImportRun`.
- Inicializador Windows otimizado para não reinstalar dependências em toda abertura quando `requirements-local.txt` não mudou.
- Atualização do `pip` passou a ser best-effort e não bloqueia a inicialização sozinha.
- Script de testes ampliado para `manage.py check` + suíte Django completa.
- Pacote limpo de caches Python, ambiente virtual, banco local, logs e segredos antes da distribuição.

## Evidência estática final
- `compileall`: aprovado.
- URLs usadas nos templates: 0 referências nomeadas ausentes.
- Delimitadores Django dos templates: consistentes.
- Parser SSW no arquivo de homologação: 2.838 linhas; 2.566 CT-es únicos; 152 CT-es únicos com retenção.

## Limitação de validação
O ambiente de empacotamento não possui Django instalado e não consegue acessar o PyPI. Portanto, a execução completa de migrations, testes Django e capturas Playwright deve ser feita no Windows pelo próprio pacote (`EXECUTAR_LOCAL.bat`, `TESTAR_SISTEMA.bat` e `CAPTURAR_TELAS.bat`). Nenhum resultado runtime foi declarado como aprovado sem ter sido executado.
