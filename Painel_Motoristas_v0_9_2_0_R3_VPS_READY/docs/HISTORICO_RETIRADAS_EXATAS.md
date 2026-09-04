# Histórico de Retiradas Exatas — v0.9.2 R2

## Princípio

A obrigação nasce da rota operacional, não da abertura do Portal. A partir de 01/09/2026, se o motorista esteve em um cliente/parada que possuía comprovante ativo naquele dia, o Painel materializa a Retirada Exata mesmo que o motorista não acesse o Portal.

## Unidade de Regularidade

A unidade é **motorista + cliente/parada + data operacional**. Vários CT-es/comprovantes no mesmo cliente e na mesma visita não multiplicam penalizações.

- qualquer manifestação válida na parada = obrigação de Regularidade cumprida;
- nenhuma manifestação até o encerramento = uma omissão;
- Ouro ignorado = neutro;
- `RETIREI` com validação pendente = não penaliza enquanto aguarda;
- `RETIREI` aprovado = cumprida;
- evidência rejeitada = não permanece como cumprimento;
- `AINDA NÃO LIBERADO` + observação = cumprida/neutra;
- `NÃO FOI POSSÍVEL TENTAR` + justificativa = cumprida/neutra.

## Backfill

O comando normal de sincronização da avaliação materializa o histórico desde o marco V3. Dias históricos já processados recebem marcador auditável e não são reconstruídos em todo startup. Importações podem forçar apenas a janela afetada.

Para determinar se o comprovante estava ativo em um dia histórico, são respeitadas origem da retenção, recuperação conhecida e `CTe.delivered_at`. O timestamp técnico em que uma reconciliação posterior marcou `RECUPERADO` não deve criar obrigação falsa para um comprovante que já constava como entregue antes.
