# Banco de Dados — V0.2.1

## Banco oficial
PostgreSQL.

## Modo local de homologação
SQLite, apenas para facilitar execução sem Docker. A modelagem/migrations deve continuar compatível com PostgreSQL.

## Entidades principais
- Driver
- Vehicle
- Client
- ClientAddress
- CTe
- Manifest (romaneio)
- DeliveryMovement
- DeliveryOccurrence
- RetainedProof
- ImportRun
- ImportStep
- GeneratedReport
- SystemSettings
- AuditLog

## Datas operacionais
A V0.2.1 não trata a data do romaneio como sinônimo da data da rota.

A **data operacional** é derivada preferencialmente de `DeliveryOccurrence` com código `85` / `SAIDA PARA ENTREGA`. Isso preserva a data real de execução mesmo quando o romaneio foi emitido em D-1.

A ocorrência permanece no histórico mesmo após `ENTREGUE`, permitindo reconstrução da rota por período sem depender do status atual.

## Identidades
- CT-e: CTRC estável.
- Motorista: CPF normalizado.
- Cliente: CNPJ quando confiável; fallback por nome normalizado com cautela.
- Endereço: `normalized_address` por cliente.
- Romaneio: número.

## Índices
Os campos de busca operacional possuem/recebem prioridade de índice: CTRC, CPF, CNPJ, datas, motorista, cliente, bairro, cidade, status de comprovante e romaneio.


## BugReport — V0.2.2
Registro persistente do Caderno de Bugs. Guarda tela, prioridade, status, descrição, reprodução, resultados atual/esperado, evidência, responsável, correção, reteste, versão e auditoria temporal. Índices principais: `(screen, status)` e `(priority, status)`.
