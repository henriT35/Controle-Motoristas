# Comprovantes Retidos — v0.5.0.0

## Data e idade
`retained_at` deve ser a data operacional real de retenção, nunca a data de importação.
- ativo: idade = corte atual/histórico − retenção;
- recuperado: tempo retido = recuperação − retenção.

## Pessoas distintas
- `original_driver`: motorista da tentativa que originou a retenção;
- `recovery_driver`: motorista que posteriormente recuperou o comprovante.

Um não sobrescreve o outro.

## Status
`AGUARDANDO_RETIRADA`, `DISPONIVEL_HOJE`, `EM_RECUPERACAO`, `AGUARDANDO_VALIDACAO`, `RECUPERADO`, `CANCELADO`.

## Registro direto por coordenador
A ação de recuperação exige motorista recuperador explícito, data, observação opcional e evidência opcional. É criada uma `ProofRecoverySubmission` aprovada e um `AuditLog`.

## Portal do motorista
Upload pelo portal gera submissão PENDING e coloca o comprovante em `AGUARDANDO_VALIDACAO`. O upload sozinho não encerra o comprovante. Um usuário autorizado valida ou rejeita.

## Filtros
Período, status, idade, motorista da retenção, motorista recuperador, cliente/busca, município, bairro, SLA e evidência. Paginação preserva querystring.

## Histórico
Consultas históricas devem usar `retained_at/recovered_at` no corte, e não o status atual indiscriminadamente.

## Atualização v0.6.0.0 — envio pelo motorista
- Motorista envia foto/PDF pelo Portal e o comprovante fica `AGUARDANDO_VALIDACAO`.
- Coordenador vê cliente, CT-e, NF, endereço, dias retidos, motorista original, motorista recuperador proposto e a evidência.
- Pode validar, rejeitar ou solicitar nova foto.
- Transações/locks impedem duas aprovações concorrentes do mesmo comprovante.

## v0.7.0.0 — origem temporal histórica

Retenções históricas usam ROM34 datado ligado ao romaneio original. Se ROM34 existe sem data, pode usar a data canônica da rota quando ela estiver comprovada. Se nenhum desses fatos existir, a origem permanece **não confirmada**; emissão/previsão persistida em `retained_at` não deve ser promovida a data histórica apenas para preencher o indicador.

Continuam obrigatórias as separações `original_driver` ≠ `recovery_driver` e submissão/evidência ≠ recuperação validada.

