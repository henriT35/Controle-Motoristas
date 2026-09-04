# Patch v0.6.0.0 — Operação, Motoristas, Comprovantes, WhatsApp e Mapa

## Base

Aplicar sobre **Painel Motoristas v0.5.0.1**.

## Principais mudanças

- Temporalidade de rota: Confirmada / Inferida / Planejada.
- Planejamento de romaneios sem afirmar data futura.
- Ranking por Qualidade + Produtividade + Confiança da amostra.
- Portal mobile com câmera/arquivo para comprovantes.
- Validação pelo coordenador com contexto e proteção concorrente.
- Central de WhatsApp Web, envio em lote e por romaneio.
- Cadastro rápido do telefone na central.
- Resolvedor geográfico Município → bairros reais da operação.
- Cache/fallback para bairros sem polígono.
- Cliente pode indicar dependência de comprovante para pagamento.
- Relatórios ampliados.

## Banco

Há novos models/campos (`WhatsAppMessage`, telefone WhatsApp do motorista e configuração de cliente). O projeto herdado gera migrations localmente no primeiro startup quando detecta alteração dos models.

Faça backup do banco antes de aplicar e deixe `EXECUTAR_LOCAL.bat` concluir `makemigrations` e `migrate`.

## WhatsApp

Execute `INSTALAR_BOT_WHATSAPP.bat` uma vez antes do primeiro uso do bot.

O bot é uma automação local de WhatsApp Web. Ele pode exigir QR novamente se a sessão do WhatsApp for encerrada. Não é API oficial da Meta e não é componente obrigatório para o restante do Painel.

## Robot SSW

O core homologado não foi alterado.
