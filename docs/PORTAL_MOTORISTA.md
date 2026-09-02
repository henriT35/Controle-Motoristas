# Portal do Motorista

## Objetivo
Oferecer acesso simplificado sem login/senha tradicional para cada motorista.

## Acesso
`/p/motorista/<token>/`

O token é aleatório, longo, único, revogável e regenerável. CPF, nome e ID sequencial não são usados como segredo de URL.

## Visão V1
- operação/rota atual do motorista;
- oportunidades de comprovantes por cliente/região compatíveis com a rota;
- histórico das próprias submissões/recuperações.

## Evidência
São aceitos formatos de imagem comuns e PDF dentro do limite definido pelo código. Um comprovante só pode ser enviado pelo portal se fizer parte das oportunidades calculadas para aquela rota/motorista.

## Validação
Portal → submissão PENDING → coordenador valida/rejeita. Não existe autoaprovação por upload.

## Segurança
Testar em ambiente real:
- token inválido;
- token revogado;
- tentativa de trocar ID do comprovante;
- motorista A tentando enviar comprovante fora das oportunidades da sua rota;
- tamanho/tipo de upload;
- enumeração de tokens.

Os testes Django foram adicionados, mas não executados neste ambiente de empacotamento.

## Atualização v0.6.0.0
- Portal mobile mostra operação confirmada e planejamento sem data afirmada.
- Upload usa câmera/galeria/PDF e sempre entra em validação.
- Coordenador pode aprovar, rejeitar ou pedir nova foto.
- Validação concorrente é protegida para impedir dupla recuperação.
- WhatsApp é apenas canal para entregar o link; o Portal continua sendo a fonte oficial.


## v0.7.0.0 — câmera mobile

O seletor único anterior combinava `accept="image/*,application/pdf"` com `capture="environment"`. Alguns navegadores móveis ignoravam a câmera nesse formato.

A interface agora separa:

- **Tirar foto** — input exclusivo `image/*` com `capture="environment"`, priorizando a câmera traseira;
- **Escolher arquivo** — galeria, imagem ou PDF, sem atributo `capture`.

O backend aceita `evidence_camera` ou `evidence_file` e mantém `evidence` como fallback de compatibilidade. A submissão continua em `PENDING` até validação do coordenador.
