# Importação SSW — V0.2.2-p2

## Fluxo

```text
arquivo .sswweb/.csv
→ parser
→ validação
→ normalização
→ comparação idempotente
→ transação
→ PostgreSQL/SQLite
→ indicadores
```

## Formas de importar

### Um arquivo
`IMPORTAR_RELATORIO_SSW.bat` copia o arquivo escolhido para `imports/inbox` e executa `manage.py import_ssw`.

### Vários meses/pasta
`IMPORTAR_LOTE_SSW.bat` abre um seletor de pasta e executa `manage.py import_ssw_batch` para todos `.sswweb`/`.csv` encontrados.

O lote tenta detectar o período dentro de cada relatório, ordena cronologicamente os arquivos válidos e continua nos demais se um arquivo falhar. O resumo mostra quantidade de arquivos, sucesso, erros, novos, atualizados, sem alteração, ignorados e comprovantes criados.

### Interface web
`/ssw/importacoes/` aceita seleção múltipla de arquivos e processa o lote mantendo idempotência.

## Regras de identidade/deduplicação
- CT-e: identificador CTRC estável.
- Motorista: CPF normalizado; linhas sem CPF recebem chave técnica estável baseada no nome normalizado.
- Cliente: CNPJ é identidade forte quando seguro; sem CNPJ, nome normalizado é usado com cautela para evitar fusões ambíguas.
- Endereço: cliente + endereço normalizado/CEP/cidade/UF.
- Romaneio: número do romaneio.
- CNPJ/CPF/CEP são normalizados para comparação sem pontuação.

## Regras temporais
Arquivos podem se sobrepor e chegar fora de ordem. A importação deve preservar histórico e evitar regressão de estado.

- CT-e já `ENTREGUE` não deve voltar para `SAIDA PARA ENTREGA` só porque um arquivo mais antigo foi importado depois.
- Romaneio `BAIXADO` não deve regredir para `PENDENTE` por reprocessamento histórico.
- Ocorrências anteriores continuam armazenadas.
- Retenção histórica mais antiga descoberta posteriormente pode retroagir a data/origem do `RetainedProof` para o evento correto.

## Rota operacional
O parser reconhece `SAIDA PARA ENTREGA` por:

```text
código 85
ou texto SAIDA PARA ENTREGA
```

A data dessa ocorrência é usada como data operacional da rota nas telas/indicadores.

## Retenção
Código 34 ou `MERCADORIA EM CONFERENCIA NO CLIENTE` cria/atualiza `RetainedProof`.

Um estado consolidado posterior `ENTREGUE` encerra a retenção ativa originada pelo SSW na data operacional da entrega. Isso não identifica quem recuperou fisicamente o comprovante: quando houver recuperação manual/validada, `recovery_driver` e a evidência permanecem fatos separados e auditáveis.

## Pagador x destinatário
O relatório não possui CNPJ explícito do destinatário. O CNPJ do pagador só enriquece o cliente quando pagador e destinatário representam a mesma entidade textual, evitando associação fiscal indevida.


## Feedback ao vivo da importação manual
A tela `/ssw/importacoes/` exibe progresso imediatamente após o envio:

1. percentual real de upload do navegador;
2. estado indeterminado durante leitura/normalização/processamento;
3. consulta periódica autenticada ao endpoint `/ssw/importacoes/progresso/`;
4. estágio corrente, arquivo e tempo decorrido;
5. recarga automática ao concluir.

O modo local continua síncrono; o indicador não inventa percentual de processamento de linhas. Durante o processamento no servidor ele mostra atividade/etapa real em vez de um percentual fictício.


## v0.3.0 — Import Engine v2
A fachada `apps.ssw.importer.import_ssw_delivery_file` utiliza o engine v2 por padrão. O mesmo pipeline é usado por upload manual e pelo arquivo devolvido pelo robô. Métricas, benchmark e rollback estão documentados em `IMPORT_ENGINE_V2.md`.
