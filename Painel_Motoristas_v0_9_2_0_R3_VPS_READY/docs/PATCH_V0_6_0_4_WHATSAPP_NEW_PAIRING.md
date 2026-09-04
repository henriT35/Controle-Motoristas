# v0.6.0.4 — WhatsApp New Device Pairing

## Sintoma
Mesmo após `Redefinir sessão`, o WhatsApp Web podia voltar para uma tela de reconexão/erro de banco como se tentasse recuperar uma sessão anterior, sem estabilizar no QR Code.

## Evidência real
O log de homologação informou que o próprio WhatsApp Web continuou apresentando erro de banco depois da reconstrução da sessão. Isso provou que repetir a estratégia de recriar o mesmo caminho de profile não era suficiente.

## Mudança
A partir da v0.6.0.4 o pareamento é transacional:

1. a sessão anterior é invalidada/quarentenada;
2. o próximo início cria `browser_profile_pairing_<timestamp>`;
3. o Chromium do Playwright é tentado primeiro;
4. o profile de pareamento só vira sessão ativa depois de o WhatsApp estar conectado;
5. tentativa que falhar não é reutilizada;
6. erro de banco gera uma segunda tentativa em outro diretório inédito.

Isso não altera o core `robot_ssw`.

## Homologação Windows
1. Instalar/preparar Playwright Chromium (`INSTALAR_BOT_WHATSAPP.bat`) se ainda não estiver instalado.
2. Central WhatsApp → Encerrar bot.
3. Central WhatsApp → Redefinir sessão.
4. Conectar WhatsApp.
5. Esperado: navegador novo → QR → escanear → Conectado.
6. Se falhar, baixar `whatsapp_bot.log` e abrir a Prévia técnica.
