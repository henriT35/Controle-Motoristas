# QA / ESTADO DA RODADA v0.9.0.0

## O que está homologado antes da v0.9
A baseline v0.8.2.0 contém as correções temporais v0.8.1.0 e scheduler/UX v0.8.2.0.

## Ambiente desta continuidade
O ambiente de empacotamento atual não possui Django instalado. Portanto não declarar execução real de `manage.py check`, migrations, servidor Windows, SSW, Baileys ou VPS nesta sessão.

## QA obrigatório quando a v0.9 for implementada
- `python -m compileall` em todos os arquivos Python;
- sintaxe JS/Node;
- `manage.py check`;
- `makemigrations --check --dry-run` ou política formal de migrations definida;
- suíte Django;
- dados reais SSW de regressão;
- visual 1920/1366/1280/1024/tablet/mobile;
- Dashboard, Operação, Motoristas, Comprovantes, Ranking;
- mapa Marituba/Abaetetuba;
- QR Baileys;
- scheduler Windows;
- Docker/VPS;
- patch dry-run;
- comparação byte a byte do `robot_ssw`.

## Casos de regressão prioritários
1. ROM34 no romaneio correto versus CTRC34 consolidado.
2. Código 13 fechando tentativa antiga.
3. CT-e reaparecendo em outro romaneio/motorista sem duplicar rota atual.
4. retenção seguida de 60/53/91 → VERIFICAR.
5. ROM sem data histórica reconstruído somente com evidência segura.
6. oportunidade regional nunca penaliza.
7. “Ainda não liberado” neutro.
8. original_driver diferente de recovery_driver preservado.
