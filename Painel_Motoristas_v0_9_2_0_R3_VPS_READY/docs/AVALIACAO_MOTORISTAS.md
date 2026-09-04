# Avaliação dos Motoristas V2

## Estado
**SIMULAÇÃO.** A v0.5.0.0 não transforma a fórmula em regra oficial de RH, remuneração ou recompensa.

## Separação obrigatória
### Produtividade
Entregas, tentativas, rotas, clientes, peso, volumes e produção por período.

### Desempenho
Taxa de sucesso, entrega limpa, retenção da tentativa, ocorrência 13, comprovantes ativos/SLA e recuperações.

## Semântica das retenções
- Retenção atribuída ao desempenho do motorista: ocorrência **ROM 34** da tentativa/romaneio.
- Comprovante ativo: estado operacional separado, reconstruído pelo corte temporal.
- Motorista da retenção e motorista recuperador não são a mesma entidade lógica.

## Ocorrência 13
`ENTREGA PREJUDICADA PELO HORARIO` é tratada como tentativa prejudicada por horário, não como “devolução” genérica.

## Nota simulada
O cálculo puro está em `apps/core/performance.py` e expõe breakdown “Por que esta nota?”. Pesos são configuráveis. Recuperação possui peso padrão zero até decisão operacional.

## Confiança da amostra
- LOW: abaixo do mínimo configurado.
- MEDIUM: de 1x até menos de 3x o mínimo.
- HIGH: a partir de 3x o mínimo.

O ranking principal usa mínimo de tentativas configurável para evitar que amostras minúsculas dominem o ranking.

## Entrega limpa
Conceito atual: entrega concluída na tentativa sem ROM34, sem ocorrência13 e sem necessidade de nova tentativa conforme os fatos disponíveis. A lista de outras ocorrências negativas não deve ser ampliada sem homologação.

## Atualização v0.6.0.0 — Qualidade, Produtividade e Confiança
- Volume não é convertido diretamente em qualidade.
- A nota usada no ranking aplica ajuste de confiança em direção à média da equipe conforme o tamanho da amostra.
- Produtividade permanece indicador independente.
- Recuperações validadas têm contribuição pequena e limitada; valor financeiro não vira ponto de qualidade.
