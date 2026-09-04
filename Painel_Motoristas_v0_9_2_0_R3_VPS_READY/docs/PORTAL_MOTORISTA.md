# Portal Web do Motorista — v0.9.2.0

Portal 100% web, acessado por token individual seguro, revogável e regenerável. Não criar aplicativo mobile nativo.

## Navegação

- Início;
- Comprovantes;
- Oportunidades;
- Ranking / Minha Avaliação;
- Perfil.

## Início

Mostra posição, Nota Geral, diferença para o motorista acima, Operação de Hoje e ações disponíveis.

## Retirada Exata

Aparece somente quando há comprovante acionável no próprio cliente/parada da rota.

- **RETIREI**: evidência obrigatória e validação do coordenador;
- **AINDA NÃO LIBERADO**: observação obrigatória, neutro;
- **NÃO FOI POSSÍVEL TENTAR**: justificativa obrigatória, neutro/auditável.

O Portal persiste a oportunidade apresentada. EXACT encerrada sem manifestação pode reduzir Regularidade; GOLD nunca.

## Oportunidade de Ouro

Regional/opcional. Ignorar é neutro. Recuperação aprovada recebe bônus maior.

## Minha Avaliação

Exibe os três pilares, eventos ROM13, Regularidade, bônus e histórico da nota. Pendência de ROM13 deve dizer explicitamente “em análise — não afeta a nota”.

## Segurança

O token não contém CPF/nome/PK. Motorista só enxerga seus próprios dados. Solicitação de novo link cria pedido para coordenador; não gera token automaticamente.
