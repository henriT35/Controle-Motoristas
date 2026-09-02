# Patch v0.6.0.2 — Cloudflare Quick Tunnel

## Base obrigatória

Painel Motoristas v0.6.0.1.

## Resultado

Painel Motoristas v0.6.0.2.

## Objetivo

Permitir que o Painel rode no próprio computador Windows e seja acessado pela Internet sem domínio próprio, usando uma URL temporária `*.trycloudflare.com`.

## Fluxo

```text
Internet
  ↓ HTTPS
Cloudflare Quick Tunnel
  ↓
cloudflared.exe no PC
  ↓ http://127.0.0.1:8000
Waitress
  ↓
Django / Painel Motoristas
  ├─ banco local/PostgreSQL
  ├─ Robô SSW
  └─ Bot WhatsApp Web
```

## Arquivos principais alterados

- `VERSION`
- `requirements.txt`
- `requirements-local.txt`
- `config/settings.py`
- `scripts/windows/common-native.ps1`
- `scripts/windows/start-native.ps1`
- `scripts/windows/stop-native.ps1`
- `scripts/windows/start-online.ps1` (novo)
- `scripts/windows/stop-online.ps1` (novo)
- `scripts/windows/show-online-url.ps1` (novo)
- `apps/core/management/commands/prepare_online.py` (novo)
- `EXECUTAR_ONLINE.bat` (novo)
- `PARAR_ONLINE.bat` (novo)
- `ABRIR_LINK_ONLINE.bat` (novo)
- documentação/CHANGELOG/README.

## Banco

Nenhuma alteração de model e nenhuma migration nova nesta versão.

## Segurança

- Waitress escuta apenas `127.0.0.1:8000`.
- O acesso externo chega pelo `cloudflared`.
- Online força `DJANGO_DEBUG=0` somente no processo publicado.
- A senha padrão `Painel@2026!` não é aceita para primeira publicação: se ainda estiver ativa, é trocada automaticamente por senha aleatória.
- A credencial gerada fica em `local_data/ONLINE_ADMIN.txt`, que é dado local e não deve ser distribuído em ZIP.
- `CSRF_TRUSTED_ORIGINS` aceita somente `https://*.trycloudflare.com` no modo online.
- O proxy confiável do Waitress é apenas `127.0.0.1`.
- `/media/` é servido no modo online por view autenticada; fotos/anexos internos não ficam acessíveis anonimamente só por conhecer a URL.

## Portal do Motorista

A URL capturada do Quick Tunnel é injetada em `PANEL_PUBLIC_BASE_URL` antes de iniciar o servidor. Mensagens geradas pelo WhatsApp passam a apontar para o endereço público atual e não para `localhost`.

## Instalação do cloudflared

O launcher tenta nesta ordem:

1. `tools/cloudflared/cloudflared.exe` dentro da instalação;
2. `cloudflared.exe` já disponível no PATH;
3. download da release oficial Windows amd64 para a pasta `tools/cloudflared`.

Nenhum binário de terceiros é empacotado nesta baseline.

## Limitações

- A URL é aleatória e temporária; pode mudar a cada recriação do Quick Tunnel.
- Se existir `config.yml`/`config.yaml` global em `%USERPROFILE%\.cloudflared`, o launcher avisa porque esse arquivo pode impedir Quick Tunnels.
- O computador precisa permanecer ligado, acordado e com Internet.
- Quick Tunnel não substitui hospedagem/URL permanente para produção de longo prazo.

## Uso

- Online: `EXECUTAR_ONLINE.bat`
- Ver/copiar URL: `ABRIR_LINK_ONLINE.bat`
- Encerrar: `PARAR_ONLINE.bat`
- Local sem Internet pública: `EXECUTAR_LOCAL.bat`
