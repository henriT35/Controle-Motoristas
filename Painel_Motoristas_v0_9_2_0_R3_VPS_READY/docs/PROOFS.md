# Comprovantes Retidos — V0.3.0.8

Regra oficial: ocorrência código `34` ou descrição `MERCADORIA EM CONFERENCIA NO CLIENTE`.

Estados: aguardando retirada, disponível hoje, em recuperação, recuperado e cancelado.

A recuperação pode ser **manual** (motorista/data/usuário/observação + `AuditLog`) ou **automática pelo SSW** quando um CT-e com histórico de código 34 passa a ter CTRC consolidado `1 / ENTREGUE`. A baixa automática usa a data/hora de `DATA/HORA OCORR CTRC` e não inventa motorista recuperador.

Validações da recuperação:
- data não pode ser anterior à retenção;
- data não pode ser futura;
- motorista original e motorista de recuperação permanecem separados.

Criticidade padrão: **mais de 15 dias** de retenção, configurável.

Oportunidades:
- exata: mesmo cliente/endereço, mesmo cliente/CEP, mesmo cliente/endereço normalizado ou mesmo CNPJ normalizado;
- regional: mesma cidade + bairro; é apenas sugestão de proximidade.

A disponibilidade de retirada no dia é cruzada com as rotas identificadas pela data operacional de `SAIDA PARA ENTREGA`.

A ocorrência `ENTREGUE` fecha automaticamente somente quando existe histórico de retenção e ela é o **estado consolidado posterior do CTRC**. `ENTREGUE` isolado sem retenção não cria comprovante.
