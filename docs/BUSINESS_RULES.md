# Regras de negócio consolidadas — V0.3.0.8

## 1. Comprovante retido — ROM x CTRC
O relatório 036 possui duas trilhas que não podem ser tratadas como equivalentes:

- `COD/DESC OCORR ROM` (Y/Z): evento daquela tentativa/romaneio; preserva histórico.
- `COD/DESC OCORR CTRC` (AC/AD): estado consolidado atual do CT-e; sua data/hora ficam em AE/AF.

Código `34` / `MERCADORIA EM CONFERENCIA NO CLIENTE` em ROM ou CTRC prova que houve retenção.

## 2. Retenção ativa x baixa automática pelo SSW
- CTRC atual em `34`: retenção continua ativa.
- Houve `34` no ROM/CTRC e o CTRC consolidado posterior está `1 / ENTREGUE`: o comprovante é marcado `RECUPERADO` automaticamente na data/hora do CTRC entregue.
- Baixa manual confirmada por usuário/motorista tem precedência e nunca é sobrescrita por reimportação.
- Se o SSW não informa a data do ROM=34, o sistema nunca usa a data da importação; usa evidência operacional histórica (saída para entrega, previsão coerente ou data do romaneio) e mantém a baixa posterior do CTRC separada.

## 3. Data operacional da rota
A data de emissão/criação do romaneio não é a data operacional obrigatória.

A fonte principal para determinar a rota do dia é a ocorrência SSW:

```text
código 85
SAIDA PARA ENTREGA
```

Exemplo:

```text
30/08 — romaneio criado
31/08 — SAIDA PARA ENTREGA
31/08 — ENTREGUE
```

A rota pertence a **31/08**. A ocorrência `ENTREGUE` não elimina o histórico de saída.

Quando `SAIDA PARA ENTREGA` existe sem data, o sistema usa fallback determinístico D+1 sobre a emissão. Movimentos legados que nunca receberam qualquer ocorrência de saída podem usar `movement_date` como fallback de compatibilidade.

### Continuidade de rota / virada de fim de semana
Uma rota pode ser preparada antes do dia em que será executada. Exemplo real: romaneio emitido/colocado em `SAIDA PARA ENTREGA` em **29/08** e ainda ativo em **31/08**.

Na V0.2.2-p2, `Operação de Hoje` também considera a rota como ativa quando, no início do dia consultado, a ocorrência mais recente do movimento ainda é `SAIDA PARA ENTREGA`. O carry-over é limitado inicialmente a **3 dias corridos** para impedir que rotas antigas fiquem presas indefinidamente. Se houver ocorrência posterior antes do início do dia (por exemplo `ENTREGUE`), a rota não é carregada para esse dia. Se a entrega acontecer durante o próprio dia consultado, a rota continua pertencendo à operação daquele dia.

## 4. Importação idempotente e temporal
Reimportar o mesmo arquivo não pode duplicar CT-es, motoristas, clientes, romaneios ou comprovantes.

Arquivos podem ser importados fora de ordem. Uma planilha histórica não deve fazer um CT-e/romaneio regredir de um estado operacional mais avançado para um estado anterior. Histórico de ocorrências é preservado.

Quando uma retenção mais antiga é descoberta em arquivo histórico importado depois, a origem/data da retenção deve ser ajustada para o evento mais antigo conhecido, sem duplicar o comprovante.

## 5. Cancelamentos
CT-e/romaneio cancelado não deve prejudicar o score do motorista.

## 6. Conferência no cliente
`MERCADORIA EM CONFERENCIA NO CLIENTE` é indicador documental/operacional e não reduz automaticamente o score do motorista.

## 7. Oportunidades de retirada
Prioridade de match exato:

1. mesmo cliente + endereço;
2. mesmo cliente + CEP;
3. mesmo cliente + endereço normalizado;
4. mesmo CNPJ normalizado.

CNPJ/CPF/CEP são comparados sem máscara/pontuação.

Match por mesma cidade + bairro é apenas **OPORTUNIDADE POR REGIÃO**, não retirada exata.

O mesmo comprovante não deve ser contado duas vezes no resumo quando puder aparecer em mais de uma rota.

## 8. Motorista original x motorista de recuperação
O motorista que originou a retenção e o motorista que recuperou o documento são campos independentes e o primeiro nunca é sobrescrito pelo segundo.

## 9. Criticidade
Default: comprovante é crítico quando está retido por **mais de 15 dias**. O limite é configurável.

## 10. Banco permanente de comprovantes
Comprovantes pendentes permanecem no banco entre meses até recuperação/cancelamento. Não há reset mensal.
