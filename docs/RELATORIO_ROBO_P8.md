# Patch p8 — Runtime do Robô SSW

Corrige o preflight para não considerar o robô pronto apenas porque a função existe.
Agora valida também URL de login quando exposta pelo robô, importação do Playwright e inicialização real do Chromium.

Inclui `PREPARAR_ROBO_SSW.bat` para instalar Playwright + Chromium no mesmo `.venv` usado pelo Painel e `DIAGNOSTICAR_ROBO_SSW.bat` para mostrar o diagnóstico e as últimas linhas do worker.

Falhas imediatas de 1–3 segundos normalmente são causadas por runtime ausente (Playwright/Chromium) ou URL do SSW não configurada, antes mesmo da navegação/seletores.
