# QA — v0.6.0.1

## Passou no ambiente de empacotamento

- Sintaxe Python.
- QA portátil.
- Performance estática do importador.
- Fórmula da avaliação V2.
- Contrato do robô SSW.
- Rotas/templates estáticas.
- Sintaxe JavaScript.
- Core `robot_ssw` inalterado.
- Limpeza de artefatos locais.
- ZIP íntegro.
- Patch aplicado sobre cópia limpa da v0.5.0.1 produz a mesma árvore funcional da release, desconsiderando docs de distribuição.

## Pendente de homologação real

- `manage.py check`.
- `makemigrations --check` depois do primeiro startup/migration local.
- `migrate --plan`.
- suíte Django.
- browser real para WhatsApp Web, portal mobile e mapa.
- banco existente com backup.


## Adendo v0.6.0.1 — WhatsApp Web

Consulte `docs/QA_RELEASE_V0_6_0_1.md`. A correção cobre QR no painel, lifecycle/heartbeat, encerramento cooperativo/forçado, redefinição de sessão e layout da Central WhatsApp.
