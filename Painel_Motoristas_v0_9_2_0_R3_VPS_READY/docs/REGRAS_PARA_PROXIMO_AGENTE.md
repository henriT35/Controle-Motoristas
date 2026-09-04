# Regras para o próximo agente — baseline v0.9.2.0

## NÃO ALTERAR sem justificativa e re-homologação

- `robot_ssw/`;
- ROM85 como evidência preferencial de saída;
- tentativa/romaneio como unidade operacional;
- ROM34 como origem histórica da retenção;
- separação `original_driver` / `recovery_driver`;
- Node.js + Baileys como WhatsApp oficial;
- proibição de usar emissão/importação para inventar rota;
- proibição de promover todas as tentativas por CTRC consolidado.

## Regras V3 que não devem regredir

- uma Nota Geral 0–100;
- pesos padrão 50/35/15 configuráveis;
- produtividade bruta fora da nota;
- ROM13 só penaliza após validação manual `DRIVER_RESPONSIBLE`;
- ROM13 pendente/VERIFY/sem responsabilidade é neutro;
- mesmo ROM13 mesma tentativa = um evento; nova tentativa com novo ROM13 pode penalizar novamente;
- ROM34 não penaliza Qualidade;
- Regularidade = ações obrigatórias cumpridas / exigidas;
- Ouro ignorado é neutro;
- “Ainda não liberado” com observação é neutro;
- “Não foi possível tentar” com justificativa é neutro/auditável;
- omissão de Retirada Exata afeta Regularidade, sem segunda punição fixa;
- auto resolução SSW não inventa `recovery_driver` nem bônus;
- CTRC atual 1/ENTREGUE encerra retenção histórica; outros estados não conclusivos ficam `ACOMPANHANDO_SSW`.

## PODE ALTERAR

UI, templates, services, cache, ranking, Portal, mapas, scheduler externo, Django WhatsApp, infraestrutura, modelos/migrations formais e relatórios — desde que preserve as regras acima.

## Antes de qualquer patch

1. copiar baseline completa;
2. alterar somente a cópia;
3. atualizar VERSION/CHANGELOG/docs;
4. rodar QA possível;
5. comparar `robot_ssw` byte a byte;
6. gerar patch contra a baseline declarada;
7. aplicar patch sobre outra cópia limpa;
8. comparar caminhos e SHA-256 com a nova baseline;
9. empacotar e gerar hashes.

## Banco

Nunca `makemigrations` automático em produção. Migrations são versionadas; rode `makemigrations --check`, `migrate --plan` e homologação em cópia do banco antes da produção.
