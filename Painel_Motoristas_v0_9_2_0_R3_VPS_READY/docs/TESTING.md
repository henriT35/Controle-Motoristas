# Testes — V0.2.2

## Executar no Windows
Depois de preparar o ambiente com `EXECUTAR_LOCAL.bat`, rode:

```text
TESTAR_SISTEMA.bat
```

O atalho executa:

```text
python manage.py check
python manage.py test
```

## Casos cobertos por testes automatizados no código
- entrega concluída derivada da ocorrência do CT-e;
- conferência no cliente sem penalização automática do score;
- acesso a Configurações protegido;
- recuperação manual persistente e auditável;
- rejeição de recuperação anterior à retenção;
- rejeição de recuperação em data futura;
- criticidade estritamente maior que o limite configurado;
- romaneio emitido em D-1 com `SAIDA PARA ENTREGA` em D0 pertencendo a D0;
- romaneio emitido e executado no mesmo dia;
- `ENTREGUE` posterior não removendo a rota da data de saída;
- fallback determinístico para saída sem data;
- contagem única de oportunidade de comprovante;
- reimportação/idempotência;
- regressão temporal de status em importação fora de ordem;
- cliente com mesmo CNPJ e variação de pontuação no nome sem duplicação;
- retenção histórica mais antiga importada depois corrigindo data/origem;
- XLSX real.

## Captura visual
Com o servidor local rodando:

```text
CAPTURAR_TELAS.bat
```

O script instala Playwright/Chromium quando necessário e captura as 12 telas em 1672×941 em:

```text
docs/homologacao/v0_2_2/
```

A captura de Operação de Hoje usa a **última data operacional** disponível, não a simples data de emissão do último romaneio.

## Estado da validação no empacotamento
A compilação estática foi executada no ambiente de geração. A suíte Django/Playwright de runtime não foi executada aqui porque Django não está instalado neste ambiente. Portanto, `TESTAR_SISTEMA.bat` + `CAPTURAR_TELAS.bat` são o fechamento de homologação no Windows.


## Caderno de Bugs — V0.2.2
Testes mínimos adicionados:
- anônimo não acessa;
- staff cria bug;
- versão é gravada;
- bug resolvido recebe `resolved_at`.
A captura Playwright inclui `caderno_bugs.png`.


## Performance v0.3.0
Execute `TESTAR_PERFORMANCE_V0_3_0.bat` após subir o ambiente local. Para benchmark de um relatório SSW sem persistir mudanças, execute `BENCHMARK_IMPORTACAO_SSW.bat`. O QA estático também garante que o Import Engine v2 não contém ORM direto dentro dos loops de linha.
