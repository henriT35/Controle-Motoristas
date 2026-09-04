# QA Release v0.7.1.1 — instalador Baileys / Node portátil

## Evidência que motivou o hotfix

O Windows conseguiu baixar e executar Node.js 24.20.0 e npm 11.19.0. O `npm install` falhou dentro do lifecycle `@whiskeysockets/baileys/engine-requirements.js` com `'node' não é reconhecido`. Isso prova que o executável estava disponível apenas pelo caminho absoluto usado pelo PowerShell, mas não pelo `PATH` herdado pelo subprocesso do npm.

## Correção validada estaticamente

- diretório do Node selecionado é prependado ao `PATH`;
- `NODE` e `npm_node_execpath` apontam para o mesmo executável;
- antes do npm existe uma prova `Get-Command node.exe` + `node.exe -v`;
- instalação parcial de `node_modules` é removida antes da nova tentativa;
- limpeza encerra somente `server.mjs` pertencente ao próprio projeto;
- dependências completas são apenas validadas, evitando reinstalação desnecessária.

## QA executado

- Python sintaxe: PASS — 179 arquivos.
- `node --check whatsapp_bridge/server.mjs`: PASS.
- `scripts/qa/portable_qa.py`: PASS — 6/6.
- `scripts/qa/test_whatsapp_baileys_static.py`: PASS, incluindo asserts do novo instalador.
- `robot_ssw`: PASS — 17/17 arquivos byte a byte idênticos à v0.7.1.0.

## Homologação Windows obrigatória

1. fechar Painel e bridge;
2. aplicar v0.7.1.1;
3. executar `INSTALAR_BOT_WHATSAPP.bat`;
4. confirmar `PATH: node.exe disponivel`;
5. confirmar conclusão do npm sem erro de `node`;
6. gerar o QR no Painel;
7. escanear, conectar e enviar uma mensagem de homologação.
