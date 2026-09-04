# Relatório de Correções — V0.2.2

Data: 31/08/2026

## Objetivo da rodada

Adicionar um **Caderno de Bugs dentro do Painel Motoristas**, para que a homologação seja registrada no próprio sistema em vez de depender de documento externo.

## Implementado

- novo app Django `apps.bugs`;
- nova tela `/bugs/`;
- item **Caderno de Bugs** na sidebar para staff/admin;
- botão contextual **Registrar bug** nas telas internas;
- seleção das telas oficiais do produto;
- prioridades P0–P3;
- fluxo de status até correção/reteste/fechamento;
- resultado atual e resultado esperado;
- passos de reprodução;
- notas técnicas, correção e reteste;
- upload de print/anexo com limite de 8 MB;
- atribuição opcional de responsável;
- captura automática da versão do sistema;
- captura de User-Agent quando ambiente não é informado;
- filtros por tela, prioridade, status e busca textual;
- KPIs do caderno;
- painel lateral de detalhes;
- edição de registros;
- auditoria de criação/alteração;
- `MEDIA_URL`/`MEDIA_ROOT` habilitados no modo DEBUG/local;
- teste automatizado básico de permissão, criação e resolução;
- captura Playwright atualizada para incluir a nova tela (12 telas no total).

## Permissão

O módulo exige usuário autenticado com `is_staff` ou superusuário.

## Banco

Novo modelo `BugReport`. O projeto continua gerando/aplicando migrations automaticamente na execução local com `makemigrations` + `migrate`.

## Observação de homologação

O módulo foi validado estaticamente no empacotamento. O teste runtime Django deve ser executado no Windows com `TESTAR_SISTEMA.bat`, seguindo o padrão do projeto.
