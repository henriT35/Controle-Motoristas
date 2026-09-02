# Patch v0.7.0.0 — Operação, Entregas, Portal e pareamento WhatsApp

## Base obrigatória
v0.6.0.6

## Escopo
- temporalidade canônica de romaneios;
- reconciliação Dashboard / Operação;
- Entregas Gerais e detalhe do CT-e;
- retenções do dia;
- persistência de contexto/filtros;
- fallback geográfico;
- câmera mobile do Portal;
- núcleo de pareamento do WhatsApp refeito com navegador normal + CDP local e tela dedicada de QR.

## Banco
Sem alteração de models e sem migration nova nesta rodada.

## Proteções
- `robot_ssw` não deve sofrer alteração;
- Portal continua por token e submissão de comprovante exige validação;
- WhatsApp continua auxiliar e desacoplado do funcionamento do Painel.

## Homologação obrigatória no Windows
1. Executar `VERIFICAR_BUILD.bat`.
2. Testar Operação/Dashboard com datas conhecidas.
3. Abrir Portal no celular por HTTPS e testar **Tirar foto** e **Escolher arquivo/PDF**.
4. WhatsApp → **Conectar / QR Code** → **Gerar QR Code**.
5. Confirmar no diagnóstico que o navegador foi iniciado em `EXTERNAL_CDP` e, preferencialmente, `navigator.webdriver=false`.
6. Escanear o QR e enviar uma mensagem de homologação.
