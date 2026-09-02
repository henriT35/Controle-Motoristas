# Patch v0.7.0.1 — WhatsApp QR direto + rota ao vivo

## Base obrigatória
v0.7.0.0

## Bugs corrigidos
1. WhatsApp: `connect_over_cdp` conectava o websocket, mas expirava antes de devolver o contexto, impedindo a geração/captura do QR. O bot agora usa CDP bruto por websocket.
2. Operação: romaneios observados atualmente como `SAIDA PARA ENTREGA` podiam permanecer em Planejamento no dia corrente quando a evidência ROMANEIO não tinha data utilizável. O estado consolidado atual confirma apenas a fotografia de hoje.

## Banco
Sem alteração de models e sem migration nova.

## Pós-atualização
- O bootstrap instalará `websocket-client>=1.8`.
- Em instalação já aberta, execute `INSTALAR_BOT_WHATSAPP.bat` se o bot acusar dependência ausente.
- Clique **Atualizar agora** para renovar o estado SSW do dia e reabra Operação de Hoje.
- WhatsApp → Conectar / QR Code → Novo pareamento → Gerar QR Code.

## Proteções
- Histórico continua sem usar CTRC para inventar data passada.
- `robot_ssw` não é alterado.
