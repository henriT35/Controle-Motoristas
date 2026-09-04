# Patch v0.6.0.1 — WhatsApp Web: QR, encerramento e layout

Base: **v0.6.0.0**.

## Corrigido

- QR Code passa a aparecer também na Central WhatsApp quando detectado na janela do navegador.
- O bot prefere Chrome/Edge instalados e mantém Chromium Playwright como fallback.
- O processo não é marcado como simplesmente Offline quando ainda está aberto porém sem heartbeat; a UI mostra **Bot sem resposta**.
- **Encerrar bot** permanece disponível enquanto houver processo e usa parada cooperativa + finalização forçada como contingência.
- **Redefinir sessão** encerra o bot, limpa somente o perfil local do WhatsApp Web e força novo QR no próximo início.
- WhatsApp Web é recarregado de forma controlada se ficar aberto sem conexão/QR.
- Log técnico persistido em `logs/whatsapp_bot.log`.
- Botão **Ver o que o bot está enxergando** permite abrir a captura atual da tela de login.
- Controles Iniciar/Encerrar acompanham o estado em tempo real.

## Visual

- Mais espaçamento entre blocos.
- Card específico de conexão/QR.
- Instruções de conexão mais claras.
- Aviso de `PANEL_PUBLIC_BASE_URL` mais compacto.
- Área de envio, tabela e blocos inferiores com hierarquia visual mais clara.

## Banco

Nenhuma migration nova neste patch.

## robot_ssw

Não alterado.
