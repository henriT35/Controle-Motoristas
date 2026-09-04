# Validação manual do ROM13 — v0.9.2.0

`13 — ENTREGA PREJUDICADA PELO HORÁRIO` é o fato inicial usado na Qualidade Operacional.

## Fluxo

1. Importação SSW encontra ROM13 na trilha ROMANEIO.
2. O sistema vincula o fato à `DeliveryMovement`/tentativa correta.
3. `DriverQualityEvent` é criado como `PENDING`.
4. Enquanto pendente, a Nota Geral não muda.
5. Coordenador avalia na Central de Avaliações.

Decisões:

- `DRIVER_RESPONSIBLE`: impacta Qualidade;
- `NOT_RESPONSIBLE`: neutro;
- `VERIFY`: neutro enquanto inconclusivo.

## Responsabilização

Para marcar responsabilidade do motorista é obrigatório informar **motivo visível ao motorista**. A observação interna é opcional e não aparece automaticamente no Portal.

A decisão registra usuário, data/hora, justificativas e auditoria.

## Idempotência e tentativas

Chave funcional: `movement + code`.

- ROM13 repetido no mesmo romaneio/tentativa = um evento;
- nova tentativa com novo ROM13 = novo evento;
- pode haver nova penalização para o mesmo motorista ou para outro motorista, se a nova ocorrência for validada;
- penalização nunca migra automaticamente da tentativa anterior.

## Reabertura

Coordenador pode reabrir uma decisão. O evento volta a `PENDING`, fica neutro, a ação é auditada e os caches/ranking são invalidados.

## Histórico

ROM13 histórico ainda não validado não pode ser transformado automaticamente em culpa. Deve permanecer pendente/não avaliado até decisão humana.
