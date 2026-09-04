# WhatsApp Motoristas — arquitetura Baileys / Node.js — v0.7.1.0

## Decisão

A partir da v0.7.1.0 o login antigo por WhatsApp Web automatizado foi **aposentado definitivamente**.

Não fazem parte do fluxo oficial de WhatsApp:

- Chrome/Edge/Chromium para pareamento;
- Playwright para WhatsApp;
- Chrome DevTools Protocol (CDP);
- `browser_profile` / IndexedDB;
- screenshots para extrair QR;
- `post_logout` como mecanismo de diagnóstico.

Playwright continua no projeto porque o **robô SSW** usa Playwright; isso não tem relação com o WhatsApp.

## Arquitetura

```text
Painel Django
   │
   ├─ Central / fila WhatsAppMessage
   │
   └─ API interna local + token
            ↓
      Node.js local
            ↓
         Baileys
            ↓
 WhatsApp Multi-Device
```

O bridge fica em `whatsapp_bridge/server.mjs`.

## QR Code

1. O coordenador abre **WhatsApp Motoristas → Conectar / QR Code**.
2. O Django inicia `node whatsapp_bridge/server.mjs`.
3. Baileys abre a conexão WebSocket do protocolo multi-dispositivo.
4. O evento `connection.update` entrega `qr` quando a conta precisa de pareamento.
5. O Node transforma essa string diretamente em `local_data/whatsapp/qr.png`.
6. O Painel mostra o PNG na tela.
7. Após o scan, `connection=open` remove o QR e muda o estado para `CONNECTED`.

Não existe navegador entre os passos 3 e 6.

## Sessão

A sessão fica em:

`local_data/whatsapp/baileys_auth/`

Ela contém credenciais e Signal keys do dispositivo vinculado e deve permanecer somente no computador servidor. `local_data/` é excluído do pacote/repositório.

**Novo pareamento** encerra o bridge, apaga somente `baileys_auth/` e exige um novo QR.

## Fila de envio

O Django continua sendo a fonte de verdade das mensagens. Ao clicar nos envios, ele cria `WhatsAppMessage` com status `PENDING`.

O Node consulta:

- `POST /whatsapp/internal/claim/`
- `POST /whatsapp/internal/result/<id>/`

As rotas:

- aceitam somente token local `Bearer` gravado em `local_data/whatsapp/bridge_token.txt`;
- exigem origem loopback;
- não são endpoints de usuário;
- marcam como `FAILED` mensagens que ficaram `SENDING` por mais de 3 minutos, evitando reenvio automático possivelmente duplicado.

O Node envia apenas texto explicitamente montado pelo Painel e devolve `SENT` ou `FAILED`.

## Privacidade

A implementação não registra listener `messages.upsert`, não responde automaticamente e não persiste conversas recebidas no Django. O WhatsApp é somente canal auxiliar para distribuir o resumo e o link do Portal.

## Instalação

Execute `INSTALAR_BOT_WHATSAPP.bat`.

O instalador:

1. procura Node.js 20+;
2. se necessário, baixa Node.js 24.20.0 LTS portátil do site oficial;
3. executa `npm install --omit=dev` em `whatsapp_bridge/`;
4. valida `server.mjs` com `node --check`.

Dependências diretas fixadas no `package.json`:

- `@whiskeysockets/baileys` 6.7.24;
- `qrcode` 1.5.4;
- `pino` 9.9.0.

## Contingência

Se o bridge estiver offline, o Painel, o SSW e o Portal continuam funcionando. O coordenador ainda pode copiar manualmente o link do motorista.

## Limitação

Baileys é não oficial e não é afiliado à Meta/WhatsApp. Mudanças no protocolo podem exigir atualização futura da dependência. Para uma integração oficialmente suportada, a alternativa de produto é WhatsApp Cloud API, que possui outro modelo de provisionamento e não usa este pareamento simples por QR.

## v0.8.0.0 — lote geral e VPS

Na VPS o Baileys roda em container separado e inicia automaticamente. Django e Node compartilham somente `local_data`, onde ficam estado, token interno e sessão `baileys_auth`.

A Central passa a oferecer **Gerar e enviar para todos** e edição do WhatsApp de qualquer motorista ativo. Para números brasileiros, o bridge consulta o WhatsApp nas formas com e sem o nono dígito após o DDD e envia para o JID realmente existente. A aplicação não adiciona leitura de conversas.

A rota `/whatsapp/internal/` é bloqueada no Nginx público; comunicação Node → Django ocorre somente pela rede interna Docker e exige token aleatório compartilhado.
