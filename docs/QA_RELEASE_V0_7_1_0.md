# QA Release v0.7.1.0 — Baileys / Node.js

## QA executado no empacotamento

- Sintaxe Python do projeto: PASS.
- `node --check whatsapp_bridge/server.mjs`: PASS.
- `node --check static/js/app.js`: PASS.
- QA portátil do projeto: PASS.
- Rotas estáticas/templates: PASS.
- Contrato/mock do robô SSW: PASS.
- Ausência dos arquivos ativos antigos `cdp_session.py` e `management/commands/whatsapp_bot.py`: PASS.
- Verificação estática do bridge: existe `connection.update`/QR/`sendMessage` e não existe listener `messages.upsert`: PASS.
- Teste de runtime com dependências mockadas: `connection.update.qr → qr.png → state=WAITING_QR → stop cooperativo`: PASS. Esse teste valida o glue do bridge, não a conexão real com o WhatsApp.

## Limitação deste ambiente

O ambiente de empacotamento não conseguiu concluir `npm install` por indisponibilidade/timeout de rede. Portanto a conexão real com o WhatsApp/Baileys não pode ser marcada como homologada aqui.

No Windows de homologação executar obrigatoriamente:

1. `INSTALAR_BOT_WHATSAPP.bat`;
2. confirmar Node 20+ e conclusão do `npm install`;
3. abrir **Conectar / QR Code**;
4. clicar **Novo pareamento**;
5. clicar **Gerar QR Code**;
6. confirmar QR visível sem abertura de Chrome/Edge;
7. escanear no celular;
8. confirmar estado `CONNECTED`;
9. enfileirar uma mensagem para número de homologação;
10. confirmar `PENDING → SENDING → SENT`;
11. reiniciar o bridge e confirmar reconexão sem novo QR;
12. usar **Novo pareamento** e confirmar que um novo QR é exigido.

## Banco/migrations

Nenhum model foi alterado nesta versão; nenhuma migration nova é esperada.
