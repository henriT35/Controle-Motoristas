# Hotfix v0.3.0.10 — identidade de clientes no Import Engine

## Erro observado em produção

Execução histórica de julho/2026 concluiu download, leitura, normalização, validação e pré-carga, mas falhou em `Persistência base` com:

`UNIQUE constraint failed: clients_client.cnpj, clients_client.name`

Isso confirma que o watchdog v0.3.0.9 passou a mostrar a etapa real do erro: o problema não era o SSW nem o arquivo de julho; era a persistência de identidade de cliente.

## Causa protegida

A versão anterior persistia novos clientes com `bulk_create`. O banco possui uma restrição única sobre `(cnpj, name)`. Se uma identidade equivalente já existisse ou surgisse entre a pré-carga e a escrita, uma única colisão abortava toda a transação mensal.

## Correção

- novos clientes agora são persistidos com `get_or_create(cnpj, name)` somente para as identidades novas do lote;
- referências em memória são remapeadas para o registro já existente quando houver conflito;
- promoção de cliente sem CNPJ para CNPJ conhecido verifica colisão antes de atualizar;
- o registro legado sem CNPJ é preservado para auditoria quando a identidade consolidada já existe;
- não é usado `ignore_conflicts`, para não mascarar outros erros de banco;
- motoristas, veículos e demais entidades continuam com persistência em lote;
- `robot_ssw` permanece inalterado.

## Resultado esperado

Reprocessar julho deve ultrapassar `Banco · identidades` sem derrubar o mês por colisão de `(cnpj, name)`. Se outro erro existir depois dessa etapa, o diagnóstico v0.3.0.9+ continuará registrando a fase exata.
