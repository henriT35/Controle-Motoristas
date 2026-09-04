# QA Release v0.6.0.2

## Escopo

Modo online sem domínio via Cloudflare Quick Tunnel.

## QA estático executado no empacotamento

- Compilação sintática dos arquivos Python.
- Validação de imports/estrutura do novo management command.
- Verificação de presença dos launchers online e scripts PowerShell.
- Verificação de que `requirements-local.txt` contém Waitress.
- Comparação SHA-256 dos 17 arquivos do `robot_ssw` com a baseline v0.6.0.1.
- Scanner do pacote final para impedir `.env.local`, banco, logs, sessão WhatsApp, `.venv` e credenciais locais.

## Homologação Windows ainda obrigatória

1. Executar `EXECUTAR_ONLINE.bat` com Internet.
2. Confirmar download/detecção do `cloudflared`.
3. Confirmar geração de URL `https://*.trycloudflare.com`.
4. Abrir login por outra rede (ex.: 4G/5G).
5. Efetuar login e testar POSTs para provar CSRF/proxy HTTPS.
6. Confirmar arquivos estáticos.
7. Abrir Central WhatsApp e testar QR.
8. Gerar um link do Portal do Motorista e confirmar que começa pela URL pública atual.
9. Enviar evidência de comprovante pelo Portal usando rede externa.
10. Encerrar por `PARAR_ONLINE.bat` e confirmar que a URL deixa de responder.
11. Iniciar `EXECUTAR_LOCAL.bat` e confirmar que nenhum túnel anterior permanece ativo.

## Resultado atual

QA estático: PASS.
Homologação Windows/rede real: PENDENTE.
