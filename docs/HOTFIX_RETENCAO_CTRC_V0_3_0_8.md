# v0.3.0.8 — Retenção x Baixa pelo CTRC

## Problema
A base tratava código 34 encontrado em ROM ou CTRC como uma pendência permanente. Quando a ocorrência de retenção vinha sem data, versões anteriores também podiam atribuir o instante de importação à retenção, produzindo datas falsas como 01/09 em documentos de meses anteriores.

## Leitura correta do relatório 036

- Y/Z (`COD/DESC OCORR ROM`) = histórico da tentativa/romaneio.
- AA/AB = data/hora da ocorrência do ROM, quando informada.
- AC/AD (`COD/DESC OCORR CTRC`) = estado consolidado do CT-e.
- AE/AF = data/hora do estado CTRC.

Regras implementadas:

1. ROM ou CTRC em 34 prova histórico de retenção.
2. CTRC atual em 34 mantém o comprovante aberto.
3. Histórico 34 + CTRC posterior `1 / ENTREGUE` marca o comprovante como `RECUPERADO` automaticamente em AE/AF.
4. Baixa manual (`confirmed_by`/`recovery_driver`) nunca é sobrescrita pelo SSW.
5. Falta de DATA OCORR ROM nunca usa a data da importação. A data histórica é inferida pela melhor evidência operacional disponível e pode ser corrigida por reimportação/reconciliação.
6. `CTe.current_status` passa a considerar a trilha `SSW_CTRC`; ocorrência do ROM não sobrescreve o estado consolidado do CT-e.

## Correção retroativa
O comando:

```bat
RECONCILIAR_COMPROVANTES_SSW_V0_3_0_8.bat
```

recalcula datas de retenção e baixa automática usando o histórico já persistido em `DeliveryOccurrence`. A operação é idempotente e preserva recuperações manuais.

## Banco
Não há alteração de schema/migration. São reutilizados `retained_at`, `status`, `recovered_at`, `note`, `confirmed_by` e `recovery_driver`.

## Robô
`robot_ssw/` não é alterado.
