# Patch v0.6.0.3 — WhatsApp Session DB / QR

## Base obrigatória

Painel Motoristas **v0.6.0.2**.

## Sintoma reproduzido pelo relato

O navegador do bot abre `web.whatsapp.com`, pede para reconectar/parear e exibe erro relacionado ao **banco de dados do navegador**. A conexão não retorna a um QR utilizável e a Central acaba voltando para um estado de reconexão/offline.

## Causa raiz no código

1. O WhatsApp Web persiste a sessão em um profile Chromium/Chrome/Edge (`local_data/whatsapp/browser_profile`) que contém IndexedDB e demais dados da sessão.
2. Quando esse armazenamento fica corrompido, o próprio WhatsApp Web pode pedir novo pareamento e não chegar ao QR normal.
3. A v0.6.0.2 tentava redefinir esse diretório com `shutil.rmtree(profile, ignore_errors=True)`. Se algum processo do navegador ainda segurasse arquivos, a exclusão podia falhar sem exceção e a UI informava sucesso mesmo reutilizando o profile defeituoso.
4. Em qualquer exceção do bot, o `finally` escrevia `OFFLINE`, apagando o `ERROR` registrado segundos antes. Isso ocultava a causa real.

## Correção

- `apps/messaging/state.py`
  - profile do bot virou constante compartilhada;
  - encerramento direcionado somente a processos cujo command line contém o `user-data-dir` exclusivo do bot;
  - reconstrução atômica do profile: renomeia/isola o antigo, cria outro limpo e não mascara diretório bloqueado.
- `apps/messaging/views.py`
  - **Redefinir sessão** só limpa depois de confirmar que o bot morreu;
  - falha de limpeza fica visível e não é tratada como sucesso.
- `apps/messaging/management/commands/whatsapp_bot.py`
  - detecta texto de erro do browser database/IndexedDB;
  - executa um auto-reparo por inicialização;
  - preserva `ERROR` depois do término;
  - amplia captura de QR para container `data-ref`, canvas e SVG.
- `static/js/app.js` / `templates/messaging/center.html`
  - estados `SESSION_DB_ERROR` e `REPAIRING_SESSION` visíveis na Central.

## Migration

Nenhuma. Models não foram alterados.

## robot_ssw

Não alterado. Comparação: **17/17 arquivos idênticos** à v0.6.0.2.

## Homologação Windows necessária

1. Aplicar sobre v0.6.0.2 ou usar a baseline completa v0.6.0.3 preservando banco/.env locais conforme procedimento normal.
2. Abrir Central WhatsApp.
3. Clicar **Redefinir sessão** uma vez para limpar o profile herdado com erro.
4. Clicar **Conectar WhatsApp**.
5. Confirmar que aparece `REPAIRING_SESSION` se a tela de database error for detectada.
6. Confirmar novo QR.
7. Escanear e confirmar `CONNECTED`.
8. Fechar/reabrir o bot e verificar persistência da sessão saudável.
9. Testar um envio de homologação.
