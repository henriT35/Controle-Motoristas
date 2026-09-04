# Retenções e estado atual do SSW — v0.9.2.0

## Dois conceitos diferentes

- **ROM34**: prova histórica de que uma tentativa/romaneio originou retenção no cliente.
- **CTRC atual**: fotografia consolidada do estado atual do CT-e no relatório 036.

ROM34 não deve permanecer como “estado eterno” do comprovante.

## Classificação

| Evidência histórica | CTRC atual | Estado do comprovante |
|---|---|---|
| ROM34 | 34 / conferência | `AGUARDANDO_RETIRADA` |
| ROM34 | 1 / ENTREGUE | `RECUPERADO`, origem `SSW` |
| ROM34 | 60/53/91/outro | `ACOMPANHANDO_SSW` |

`ACOMPANHANDO_SSW` sai das Retiradas Exatas e não penaliza motorista. A próxima importação reavalia automaticamente.

## Datas retrocorrigidas

O SSW pode corrigir a data de entrega para trás e relatórios antigos podem não conter `DATA OCORR ROM`. O sistema não pode usar um horário técnico inferido (ex.: 12:00) para vetar um estado atual `ENTREGUE`.

A data de entrega é preservada como evidência, mas o **estado consolidado atual** governa se a retenção ainda é acionável.

## Importação fora de ordem

O engine v2 também protege contra arquivo antigo importado depois de um relatório de tentativa mais nova. O snapshot do arquivo é associado à data operacional da tentativa; snapshots claramente mais antigos não regridem a fotografia atual já persistida.

## Resolução automática não é recuperação premiada

Ao resolver por CTRC `ENTREGUE`:

- `status=RECUPERADO`;
- `resolution_source=SSW`;
- `recovery_driver=NULL`;
- `confirmed_by=NULL`;
- nenhum bônus é criado.

Bônus exige recuperação explicitamente atribuída, evidência e aprovação do coordenador.

## Casos de regressão reais

### BNU046259-4

ROM34 histórico sem data/hora, CTRC atual `1 ENTREGUE` em 15/01/2026 11:02. O antigo fallback de retenção em 12:00 não pode fazer o sistema concluir que a entrega “veio antes”. Resultado correto: resolvido.

### CWB055520-7

ROM34 real aparece depois da data de entrega retrocorrigida no snapshot, mas CTRC atual é `1 ENTREGUE`. Resultado correto: resolvido; não exigir opção 101 para rotina normal.

## Reconciliação

Dry-run:

`python manage.py reconcile_retained_proofs --dry-run`

Aplicação:

`python manage.py reconcile_retained_proofs`

O comando é idempotente, audita mudanças e preserva origem da retenção.
