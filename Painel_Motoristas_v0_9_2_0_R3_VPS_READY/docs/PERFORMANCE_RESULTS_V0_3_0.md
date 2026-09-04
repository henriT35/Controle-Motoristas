# Performance Results — v0.3.0

## Resultado medido nesta construção

### CPU — normalização do relatório real
50 repetições sobre 2.838 linhas:

- baseline média: **0,121342 s**;
- v0.3.0 média: **0,034212 s**;
- ganho médio: **71,80%**;
- baseline mediana: **0,121585 s**;
- v0.3.0 mediana: **0,030842 s**;
- ganho mediano: **74,63%**.

Esse número mede somente CPU dos helpers de normalização/parsing usados no pipeline, não banco/Django.

## Resultado estrutural
- Import Engine v1: processamento linha a linha chamava helpers com ORM individual.
- Import Engine v2: QA AST confirma **zero chamadas ORM diretas dentro dos loops de linha**.
- v2 contém `bulk_create`, `bulk_update` e `transaction.atomic`.
- core do Robô SSW: hashes 6/6 preservados.
- código Python completo: `compileall` aprovado.
- golden parser: 2.838 linhas, 2.566 CT-es únicos, 152 CT-es retidos e 18 romaneios com saída para entrega permanecem como referência.

## Métricas runtime pendentes de máquina real
O ambiente de construção não possui Django instalado e não tem acesso de rede ao PyPI, por isso não foram fabricados tempos/queries de views. A versão entregue inclui:

```text
TESTAR_PERFORMANCE_V0_3_0.bat
BENCHMARK_IMPORTACAO_SSW.bat
python manage.py benchmark_system
python manage.py benchmark_ssw_import
python manage.py healthcheck
```

Esses comandos produzem a parte runtime do antes/depois no Windows do usuário.
