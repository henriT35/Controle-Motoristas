> **Regra superada na v0.3.0.8:** a validação do relatório real 036 mostrou que ROM e CTRC têm papéis distintos. Histórico ROM=34 + CTRC posterior 1/ENTREGUE representa baixa automática; recuperação manual continua soberana.

# Import Turbo — v0.3.0.2

Objetivo: reduzir o tempo percebido e real entre `DOWNLOADED` e a aplicação dos dados SSW, sem alterar o core homologado do robô nem as regras de negócio.

## Diagnóstico

No arquivo real de homologação (`2.838` linhas), a leitura CSV pura levou cerca de **0,023 s** neste ambiente. Portanto, esperas longas rotuladas como “leitura” pertencem principalmente às etapas de normalização/ORM/persistência, não ao `csv.reader`.

## Mudanças

- progresso técnico em `local_data/import_progress/run_<id>.json`, fora da transação SQLite;
- UI mostra fase real: leitura, normalização, pré-carga, identidades, endereços, romaneios, CT-es, movimentos, ocorrências e comprovantes;
- o polling não força mais reload da página a cada mudança de etapa;
- cada linha percorre as ocorrências uma única vez (antes eram três passes para ocorrência/retenção/saída de rota);
- removidas duas pré-consultas não utilizadas (romaneios e CT-es);
- removidas recargas incondicionais de motoristas, veículos, clientes, endereços, romaneios, CT-es e movimentos quando o backend retorna PKs no `bulk_create`;
- endereços são pré-carregados apenas para as chaves normalizadas presentes no lote;
- histórico de ocorrências afetado é lido uma única vez; o status cronológico é recalculado com `existing + new` em memória;
- mantém `transaction.atomic()` para o lote operacional;
- mantém `ENTREGUE != comprovante recuperado` e não sobrescreve dados manuais de recuperação;
- qualquer período manual acima de 31 dias passa a ser quebrado em janelas mensais, independentemente do tipo selecionado.

## Medição local sem banco

Arquivo de homologação:

- leitura CSV média: ~0,023 s;
- derivação de ocorrências antiga (3 passes): ~0,00946 s / 2.838 linhas;
- derivação nova (1 passe): ~0,00416 s / 2.838 linhas;
- redução nessa microetapa: ~56%.

Esses valores não representam o tempo total da importação. O ganho de banco deve ser medido na máquina do projeto com:

```bat
BENCHMARK_IMPORT_TURBO.bat
```

O comando mostra leitura, normalização, pré-carga, comparação, banco, queries e memória.
