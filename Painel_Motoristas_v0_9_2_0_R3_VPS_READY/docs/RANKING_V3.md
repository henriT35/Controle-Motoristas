# Ranking V3 — v0.9.2.0

## Regra oficial

Existe **uma Nota Geral (0–100)**. Os três pilares explicam a nota; não são rankings concorrentes.

| Pilar | Peso padrão | O que mede |
|---|---:|---|
| Gestão de Comprovantes | 50% | Tratamento correto das ações de comprovante atribuíveis ao motorista |
| Qualidade Operacional | 35% | Proporção de tentativas sem ROM13 validado como responsabilidade do motorista |
| Regularidade | 15% | Constância no cumprimento das ações obrigatórias realmente exigidas |

Pesos ficam em `SystemSettings` e devem somar 100%.

## Produtividade

CT-es, entregas, peso, toneladas, frete, volume, paradas e romaneios são **estatísticas operacionais**. Não entram diretamente na Nota Geral porque motoristas recebem cargas, veículos e rotas diferentes.

## Qualidade proporcional

A fórmula é:

`Qualidade = (tentativas - ROM13 responsáveis validados) / tentativas × 100`

Exemplos:

- 50 tentativas / 2 falhas validadas = 96%;
- 300 tentativas / 12 falhas validadas = 96%;
- 300 tentativas / 2 falhas validadas = 99,33%.

Volume maior não gera bônus; apenas torna a amostra mais estável. A elegibilidade do ranking continua condicionada à amostra mínima configurável.

## ROM13

ROM13 nunca penaliza automaticamente. O evento nasce `PENDING` e só o estado `DRIVER_RESPONSIBLE`, decidido pelo coordenador, entra na taxa de falhas.

- `PENDING`: neutro;
- `NOT_RESPONSIBLE`: neutro;
- `VERIFY`: neutro;
- `DRIVER_RESPONSIBLE`: uma falha naquela tentativa.

Mesmo fato repetido na mesma tentativa não duplica. Novo ROM13 em nova tentativa pode gerar nova penalização após nova validação.

## ROM34

ROM34 não participa da Qualidade. Ele é origem/evidência de retenção de comprovante.

## Regularidade

`Regularidade = ações obrigatórias cumpridas / ações obrigatórias avaliáveis × 100`

Entram apenas obrigações persistidas e apresentadas/prospectivas após o marco de ativação V3. Ouro ignorado não entra.

## Gestão de Comprovantes

A idade do comprovante não vira culpa automática. O pilar avalia respostas/recuperações atribuíveis ao motorista. Omissão de Retirada Exata pertence à Regularidade para evitar dupla penalização.

## Bônus

Bônus padrão configuráveis:

- Retirada Exata validada: +0,30;
- Ouro validado: +0,90;
- teto total: +5,00.

Somente recuperação aprovada conta; mérito é do `recovery_driver` real.

## Transparência

O Portal deve responder “por que estou nessa posição?” com:

- período e número de tentativas;
- três pilares e contribuições;
- eventos que reduziram a nota;
- eventos neutros;
- pendências em análise;
- bônus;
- projeção baseada na fórmula atual.
