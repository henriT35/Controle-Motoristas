# Entregas Gerais — v0.7.0.0

## Objetivo

Centralizar a consulta operacional dos CT-es/tentativas sem misturar o conceito com a Central de Comprovantes Retidos.

## Fonte temporal

A lista padrão contém movimentos de romaneios cuja **data operacional canônica** pertence ao período consultado. Emissão do romaneio não é data operacional. Romaneio sem evidência permanece como planejamento/data não confirmada e não contamina KPIs históricos.

## Filtros

Período, busca por CT-e/NF/cliente/romaneio, motorista, cliente, romaneio, município, bairro, ocorrência, entregue/não concluído, primeira tentativa/reentrega, retenção, status do comprovante e ordenação. A filial exibida corresponde à base/deployment ativo; a baseline ainda não suporta separar múltiplas filiais históricas dentro da mesma base.

## Colunas e detalhe

A tabela apresenta data operacional/confiança, CT-e/NF, cliente, motorista, romaneio, região, peso/volumes, tentativas, entrega e comprovante. O CT-e abre a ficha unificada com documento, valores, tentativas, endereços, ocorrências ROM/CTRC e comprovantes/evidências.

## Navegação

Filtros são representados na querystring e o menu lateral memoriza a última URL consultada por módulo durante a sessão. O detalhe recebe `next` seguro para retornar ao contexto anterior.
