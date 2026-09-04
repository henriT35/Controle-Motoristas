# Patch v0.7.1.1 — instalador Baileys

Base: **v0.7.1.0**.

Este patch não muda o core Baileys. Corrige somente a preparação local no Windows quando Node.js é baixado de forma portátil.

## Causa

O `npm.cmd` era chamado por caminho absoluto, mas os lifecycle scripts das dependências chamavam `node` pelo `PATH`. O diretório `tools/node` não estava no `PATH`, portanto a instalação abortava.

## Aplicação

Após aplicar o patch, basta rodar novamente `INSTALAR_BOT_WHATSAPP.bat`. O Node portátil já baixado será reutilizado. O instalador tentará remover o `node_modules` parcial deixado pela tentativa anterior.
