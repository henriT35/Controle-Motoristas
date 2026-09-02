# QA Release v0.6.0.5

## QA portátil executado

- compilação de todos os arquivos Python;
- `node --check static/js/app.js`;
- validação estática das URLs/handlers novos;
- teste unitário portátil do parser `post_logout=1&logout_reason=0`;
- comparação byte a byte do diretório `robot_ssw` contra v0.6.0.4;
- scanner do ZIP final para banco/.env/logs/sessões/cache;
- teste de extração do ZIP e recompilação.

## Homologação Windows ainda obrigatória

1. Encerrar bot.
2. Redefinir sessão.
3. Conectar WhatsApp.
4. Confirmar profile novo.
5. Se Chromium cair em post_logout, confirmar troca automática para Chrome/Edge.
6. Confirmar que QR aparece em pelo menos um navegador ou, se todos falharem, baixar `whatsapp_bootstrap.jsonl`.
7. Após QR, confirmar promoção da sessão e reconexão posterior.

QA portátil não substitui o teste real com WhatsApp Web/Windows.
