# Regularidade — v0.9.2.0

Regularidade mede **constância no cumprimento das ações operacionais obrigatórias**. Não mede produtividade nem dias trabalhados.

## Fórmula

`Regularidade = cumpridas corretamente / ações obrigatórias avaliáveis × 100`

A janela é configurável por `driver_v3_regularity_window_days` (padrão 30 dias).

Se não houve nenhuma ação obrigatória no período, a Regularidade fica neutra em 100; dias sem obrigação não entram no denominador.

## Ações cumpridas

- Retirada Exata → `RETIREI`;
- Retirada Exata → `AINDA NÃO LIBERADO` + observação;
- Retirada Exata → `NÃO FOI POSSÍVEL TENTAR` + justificativa;
- ressalva de retenção prospectiva registrada corretamente.

## Omissão

Uma Retirada Exata só pode virar omissão quando existe registro persistente de que foi efetivamente apresentada ao motorista e a data operacional já encerrou sem resposta.

A omissão reduz **Regularidade**, não gera uma segunda penalização fixa na Gestão de Comprovantes.

## Ouro

Oportunidade de Ouro é opcional. Se expirar sem resposta vira `EXPIRED_NEUTRAL` e nunca entra no denominador.

## ROM13 / ROM34

ROM13 não entra na Regularidade porque pertence à Qualidade. ROM34, como ocorrência, não reduz Regularidade; apenas a obrigação prospectiva de registrar uma ressalva pode ser avaliada.

## Proteção histórica

`driver_v3_actions_activation_date` marca quando obrigações V3 começaram a ser materializadas. ROM34 anterior a esse marco não pode virar penalização retroativa.
