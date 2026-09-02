# Patch v0.6.0.6 — WhatsApp durableStorage

## Base
Obrigatória: v0.6.0.5.

## Evidência
O arquivo de diagnóstico real `whatsapp_bootstrap.jsonl` mostrou profiles novos, Chromium/Chrome abrindo normalmente e o console do WhatsApp emitindo `storage bucket persistence denied` imediatamente antes de `post_logout=1&logout_reason=0`. Isso desloca a causa do simples reaproveitamento de sessão para a permissão de armazenamento persistente exigida durante o bootstrap do WhatsApp Web.

## Implementação
- `Browser.setPermission` via CDP com `persistent-storage=granted` (Chromium `durableStorage`) para `https://web.whatsapp.com`, antes do `page.goto`.
- Telemetria segura do estado de `persistent-storage`, `navigator.storage.persisted()`, IndexedDB e quota.
- Fallback por navegador também para `BrowserSessionDatabaseError` em pareamento novo.
- Código de diagnóstico `WHATSAPP_STORAGE_DENIED`.

## Arquivos de runtime alterados
- `apps/messaging/management/commands/whatsapp_bot.py`

## Banco
Sem mudança de models. Sem migration.

## robot_ssw
Não alterado.
