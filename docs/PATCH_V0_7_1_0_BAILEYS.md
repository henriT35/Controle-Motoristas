# v0.7.1.0 — substituição definitiva do login WhatsApp por Baileys

## Motivo

Após múltiplas tentativas de estabilizar QR via navegador, a homologação Windows continuava falhando em pontos diferentes do bootstrap do WhatsApp Web: storage/IndexedDB, `post_logout`, `connect_over_cdp` e CDP bruto.

A causa arquitetural era a dependência do navegador para uma tarefa que não precisa de navegador.

## Mudança

O módulo foi substituído por um bridge **Node.js + Baileys**. O QR vem diretamente de `connection.update.qr`, sem DOM, canvas, screenshot ou navegador.

Arquivos antigos retirados do caminho oficial:

- `apps/messaging/cdp_session.py` — removido;
- `apps/messaging/management/commands/whatsapp_bot.py` — removido.

Novos componentes:

- `whatsapp_bridge/package.json`;
- `whatsapp_bridge/server.mjs`;
- `scripts/windows/install-whatsapp-baileys.ps1`;
- `scripts/windows/start-whatsapp-baileys.ps1`;
- API interna de fila em `apps/messaging/views.py`.

## Banco

Sem alteração de models. **Nenhuma migration nova.**

## robot_ssw

Não deve haver alteração. Validar por hash antes da entrega.
