# PATCH VPS READY — v0.9.2.0 R3

Este arquivo também acompanha a baseline completa para que o dry-run do patch seja byte a byte reproduzível.

O patch `PATCH_Painel_Motoristas_v0_9_2_0_R3_VPS_READY.zip` deve ser aplicado somente sobre a baseline `Painel_Motoristas_v0_9_2_0_BASELINE_COMPLETA_OTIMIZADA_R3`.

Ele altera somente a camada de implantação/infraestrutura e um comando externo de sincronização para evitar warmup duplicado. `robot_ssw/` permanece congelado.
