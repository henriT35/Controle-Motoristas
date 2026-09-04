# Patch v0.6.0.5 — WhatsApp bootstrap / post_logout

## Problema reproduzido

Mesmo usando profile de pareamento inédito, o navegador abria `https://web.whatsapp.com/` e o próprio WhatsApp Web redirecionava para `?post_logout=1&logout_reason=0` antes de exibir QR. Portanto o problema não era apenas captura de QR ou reutilização de IndexedDB.

## Causa técnica tratada nesta versão

A v0.6.0.4 tinha fallback de navegador somente quando o executável falhava ao abrir. Um navegador que abria com sucesso, porém era rejeitado durante o bootstrap do WhatsApp, era considerado válido e o fluxo não avançava para os demais navegadores.

A v0.6.0.5 passa a tratar a página do WhatsApp como parte da validação do navegador. `post_logout` antes do QR invalida aquela tentativa.

## Fluxo novo

1. Criar profile de pareamento inédito.
2. Abrir Chromium Playwright.
3. Navegar explicitamente para `https://web.whatsapp.com/`.
4. Se chegar ao QR, aguardar pareamento.
5. Se cair em `post_logout`, fechar o contexto e não reutilizar o profile.
6. Criar outro profile inédito e tentar Google Chrome.
7. Repetir com Microsoft Edge, se necessário.
8. Só promover um profile quando `CONNECTED` for realmente detectado.

## Diagnóstico

Arquivo: `logs/whatsapp_bootstrap.jsonl`.

Registra por execução:
- navegador/profile tentado;
- navegação do frame principal;
- URL sanitizada;
- `post_logout` e `logout_reason`;
- console warning/error;
- erros JavaScript;
- requests falhas;
- respostas HTTP >=400 de domínios relacionados ao WhatsApp;
- WebSocket aberto/fechado;
- User-Agent, plataforma, idioma, `navigator.webdriver`, estado online/cookies.

Não registra mensagens de conversas. Querystrings são removidas, exceto os campos de diagnóstico `post_logout` e `logout_reason`, e sequências longas/tokens são redigidas.

## Banco/migrations

Nenhuma alteração de model. Nenhuma migration nova.

## robot_ssw

Não alterado.
