# Patch p12 — Botão PLAY do login SSW

## Causa
O login real do SSW apresenta os quatro inputs e um controle PLAY separado entre a senha e o checkbox. Esse controle não aparece como `input[type=image]` nos inputs diagnosticados e pode ser um `a`/elemento com `onclick`.

## Correções
- suporte a links com ►/▶;
- busca por `a[onclick]` e controles de login;
- fallback pelo controle clicável visualmente mais próximo à direita da senha;
- fallback de teclado TAB + ENTER;
- espera de até 15 s pela transição real do login;
- diagnóstico de controles clicáveis em `login_acoes*.json`;
- build do robô atualizado para `1.2.0-p12`.

## Teste
Execute `TESTAR_LOGIN_ROBO_SSW.bat` antes de testar a opção 036.
