# Performance Baseline — v0.3.0

## Objetivo
Baseline da rodada **Performance & Stability**. O core homologado do Robô SSW não faz parte da refatoração funcional; a medição do Painel começa na entrega do arquivo ao importador.

## Ambiente de medição disponível nesta construção
- Amostra real SSW de homologação: 2.838 linhas válidas.
- CT-es distintos conhecidos: 2.566.
- CT-es retidos distintos: 152.
- Romaneios com `SAIDA PARA ENTREGA`: 18.
- Python do ambiente de construção: 3.13.5.
- O ambiente de construção não contém Django instalado e não possui acesso ao PyPI; portanto **tempo/query count de views Django não foi inventado**. A versão inclui comandos para coletar esses números no Windows onde o sistema roda.

## Gargalo estrutural encontrado — Import Engine v1
O motor antigo processava cada linha chamando helpers que por sua vez executavam ORM individual:

- `Driver.get_or_create()`;
- `Vehicle.get_or_create()`;
- criação/resolução de Client e `ClientAddress.get_or_create()`;
- `Manifest.get_or_create()`;
- `CTe.get_or_create()`;
- `DeliveryMovement.get_or_create()`;
- `DeliveryOccurrence.get_or_create()`;
- `RetainedProof.get_or_create()`;
- vários `.save()` e consultas de última ocorrência.

Logo, o número de operações SQL crescia aproximadamente com o número de linhas/entidades.

## Gargalos web encontrados por revisão de código
- Operação de Hoje buscava todos os comprovantes abertos novamente para **cada romaneio**.
- Operação de Hoje carregava os movimentos para os cards e depois fazia uma segunda consulta aos mesmos movimentos para KPIs/regiões.
- Perfil do Motorista executava uma consulta operacional separada para cada um dos 12 meses.
- Clientes fazia `filter()` em uma relação já prefetchada, invalidando o benefício do prefetch e podendo gerar N+1.
- Comprovantes executava múltiplos `count()` independentes para os KPIs.
- Histórico SSW carregava todas as execuções finalizadas em Python apenas para calcular duração média.
- Configuração singleton era consultada repetidamente em uma mesma sequência de requests.
- `makemigrations` era executado em toda inicialização Windows.

## Baseline CPU dos helpers de normalização
Carga sintética baseada nas 2.838 linhas reais, executando normalização de cliente/bairro/endereço/pagador, decimais, volume, data e ocorrências, 50 repetições:

| Métrica | v0.2.2 | v0.3.0 |
|---|---:|---:|
| média | 0,121342 s | 0,034212 s |
| mediana | 0,121585 s | 0,030842 s |

O resultado pós-refatoração aparece também em `docs/performance/NORMALIZATION_BENCHMARK.json`.

## Coleta runtime no Windows
Após abrir o sistema:

```bat
TESTAR_PERFORMANCE_V0_3_0.bat
```

Para o importador:

```bat
BENCHMARK_IMPORTACAO_SSW.bat
```

O benchmark do importador faz rollback por padrão e não altera o banco.
