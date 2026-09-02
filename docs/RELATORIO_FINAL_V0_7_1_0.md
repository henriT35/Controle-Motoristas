# Relatório final — v0.7.1.0 — WhatsApp Baileys / Node.js

## Problema

O QR do WhatsApp permaneceu instável por várias versões porque o desenho dependia do bootstrap de um navegador real/automatizado. Foram observadas falhas distintas em IndexedDB/storage, `post_logout`, Playwright CDP e CDP bruto.

## Decisão

A v0.7.1.0 elimina essa dependência. O WhatsApp passa a ser um serviço local Node.js com Baileys, que implementa o protocolo multi-dispositivo por WebSocket e entrega a string do QR diretamente.

## Fluxo final

```text
Coordenador → Gerar QR
               ↓
Django inicia Node
               ↓
Baileys connection.update.qr
               ↓
qrcode → local_data/whatsapp/qr.png
               ↓
Django mostra o QR
               ↓
scan no celular
               ↓
Baileys salva credenciais em local_data/whatsapp/baileys_auth
```

Depois do pareamento, o mesmo processo consulta a fila local do Django e usa `sock.sendMessage` apenas para mensagens explicitamente criadas pelo Painel.

## Segurança

- bridge não é publicado em porta HTTP própria;
- comunicação Node → Django usa endpoints internos com Bearer token aleatório local;
- token e sessão ficam em `local_data/`;
- não existe listener de mensagens recebidas;
- não existe resposta automática;
- Portal continua autenticado por token próprio e independente do WhatsApp.

## Compatibilidade

- sem migration;
- `robot_ssw` não deve mudar;
- Playwright continua instalado exclusivamente porque é usado pelo SSW/captura de telas do projeto, não pelo WhatsApp.

## Homologação pendente

A instalação npm e o scan real devem ser executados no Windows. O ambiente de empacotamento não concluiu o download npm por timeout de rede, portanto não se declara a conexão real como PASS.
