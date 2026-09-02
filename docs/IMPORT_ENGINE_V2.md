# Import Engine V2

## Princípio
O motor v2 remove o padrão ORM-por-linha e implementa um pipeline explícito:

```text
Arquivo
→ parse único
→ normalização em memória
→ extração de chaves
→ preload do banco
→ comparação em memória
→ bulk_create / bulk_update
→ ocorrências
→ comprovantes retidos
→ refresh cronológico de status
→ commit
```

## Compatibilidade
A API pública continua sendo:

```python
from apps.ssw.importer import import_ssw_delivery_file
```

O `importer.py` funciona como fachada. Por padrão usa `v2`. Rollback temporário:

```env
SSW_IMPORT_ENGINE=v1
```

O motor manual e o retorno do Robô SSW continuam usando a mesma função pública.

## Otimizações principais
- nenhum `get_or_create()` no loop quente por linha; a identidade de clientes novos usa `get_or_create(cnpj, name)` apenas sobre o conjunto deduplicado de identidades do lote, conforme hotfix v0.3.0.10;
- nenhum acesso ORM direto dentro dos loops de linha, verificado por AST no QA estático;
- preload de drivers, veículos, clientes, romaneios e CT-es;
- dicionários/sets para lookup O(1);
- `bulk_create`/`bulk_update` com lote de 1.000;
- parsing e normalização antes da transação;
- persistência dentro de `transaction.atomic()`;
- ocorrências preloaded somente para CT-es afetados;
- atualização de status pela cronologia das ocorrências, não pela ordem de importação;
- comprovantes retidos tratados em lote;
- primeira/última visita de cliente atualizadas em bulk;
- não há delete/recreate do histórico.

## Regras preservadas
- CTRC continua chave de negócio do CT-e.
- CPF continua identidade do motorista.
- `SAIDA PARA ENTREGA` continua definindo data operacional.
- arquivo antigo não regride `ENTREGUE` para ocorrência anterior.
- código 34 / `MERCADORIA EM CONFERENCIA NO CLIENTE` cria retenção.
- um estado CTRC posterior `ENTREGUE` fecha a retenção ativa de origem SSW na data operacional da entrega; recuperação manual validada continua preservada e nunca é apagada pelo reprocessamento.
- recuperação manual não é sobrescrita pelo SSW.
- motorista original e motorista de recuperação permanecem separados.

## Métricas persistidas
`ImportRun` passou a guardar:

- `parse_seconds`;
- `normalize_seconds`;
- `preload_seconds`;
- `compare_seconds`;
- `database_seconds`;
- `postprocess_seconds`;
- `total_seconds`;
- `rows_read`;
- `rows_valid`.

Esses campos aparecem no histórico técnico da execução.

## Benchmark

```bash
python manage.py benchmark_ssw_import caminho\relatorio.sswweb --repeat 3
```

Por padrão usa transação externa e rollback. Use `--commit` somente quando desejar persistir a importação do benchmark.
