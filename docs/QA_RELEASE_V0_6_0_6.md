# QA Release v0.6.0.6

## QA portátil
- Sintaxe de todos os `.py`: PASS.
- JavaScript com `node --check`: PASS quando Node disponível no empacotamento.
- `robot_ssw` comparado byte a byte com v0.6.0.5: PASS, 17/17 idênticos.
- Nenhuma migration nova.
- ZIP extraído e revalidado: PASS.

## Homologação Windows obrigatória
1. Encerrar bot.
2. Redefinir sessão.
3. Conectar WhatsApp.
4. Confirmar no `whatsapp_bootstrap.jsonl` evento `durable_storage_permission_override` com `result=ok`.
5. Confirmar em `bootstrap_metadata` `persistentStoragePermission=granted` e/ou `storagePersisted=true`.
6. Confirmar que o WhatsApp chega ao QR e não entra em `post_logout`.
7. Escanear QR e confirmar `CONNECTED`.

Este ambiente de empacotamento não substitui a homologação do Chrome/Edge/Chromium real no Windows.
