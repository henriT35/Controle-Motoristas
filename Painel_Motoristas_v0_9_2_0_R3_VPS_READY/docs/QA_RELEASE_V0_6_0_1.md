# QA — v0.6.0.1

## Escopo

Correção do módulo WhatsApp Web: QR, ciclo de vida do processo, encerramento e refinamento visual.

## Verificações executadas no ambiente de empacotamento

- Sintaxe Python: **177 arquivos / 0 erros**.
- JavaScript: **2 arquivos / 0 erros** (`node --check`).
- QA portátil: **6 PASS / 0 FAIL**.
- Rotas estáticas de templates: **PASS — 51 nomes conhecidos, 0 referência órfã**.
- Fórmula da avaliação V2: **PASS**.
- Performance estática: **PASS**.
- `robot_ssw`: **17/17 arquivos idênticos à v0.6.0.0**.

## Cenários cobertos por implementação

1. Bot offline → iniciar.
2. Processo aberto sem heartbeat → estado `UNRESPONSIVE`, mantendo Encerrar disponível.
3. Espera de login/QR não fica 60s sem heartbeat.
4. QR detectado → screenshot autenticado exibido no Painel.
5. QR expirado → tentativa de recarga.
6. Tela sem QR → reload controlado após 30s.
7. Encerrar → stop request cooperativo; fallback `taskkill /T /F` no Windows.
8. Sessão local presa → Redefinir sessão remove somente o browser profile.
9. Log do processo persistido em `logs/whatsapp_bot.log`.
10. Chrome → Edge → Chromium como ordem de fallback do navegador.

## Pendente de homologação Windows real

- Escanear QR em navegador real.
- Confirmar persistência da sessão após fechar/reabrir bot.
- Confirmar envio para um número de homologação.
- Confirmar encerramento durante `WAITING_QR`.
- Confirmar encerramento durante fila vazia e durante envio.
- Testar `Redefinir sessão` e geração de QR novo.

Nenhum desses itens foi declarado como PASS sem execução no Windows real.
