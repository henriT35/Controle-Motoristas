# Relatório — v0.6.0.1

**Base:** v0.6.0.0  
**Objetivo:** corrigir conexão do Bot WhatsApp Web e refinar a Central WhatsApp.

## Causa técnica observada

O estado visual considerava o bot offline após 25 segundos sem heartbeat. Operações bloqueantes do navegador podiam ultrapassar esse intervalo, deixando a interface dizer **Offline** mesmo com processo/browser ainda aberto. Além disso, o JavaScript atualizava título/ícone, mas não alternava os botões Iniciar/Encerrar em tempo real.

O processo também descartava stdout/stderr em `DEVNULL`, dificultando diagnosticar por que o WhatsApp Web não chegava ao QR.

## Correção

- Processo vivo é separado de heartbeat responsivo.
- Processo vivo sem heartbeat vira `UNRESPONSIVE`, nunca “offline silencioso”.
- QR e screenshot da tela de login são capturados pelo processo.
- Parada cooperativa por arquivo de stop e fallback de kill da árvore.
- Redefinição explícita da sessão local.
- Chrome/Edge preferenciais e Chromium como fallback.
- Log persistente.
- Layout de conexão/QR reorganizado.

## Banco

Nenhuma migration nova.

## robot_ssw

17/17 arquivos idênticos à base v0.6.0.0.
