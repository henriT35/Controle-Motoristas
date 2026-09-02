# Robô SSW — p10 — Teste isolado de login

## Motivo

O erro exibido pelo Painel era `LOGIN_SELECTOR: Campo de usuário não encontrado na tela de login.`.
Essa mensagem pertence ao código antigo do robô v1.1/p8 e não existe no robô p9/p10.

## Mudanças

- marcador de build `ROBOT_BUILD = 1.2.0-p10`;
- login com Domínio + CPF + Usuário + Senha;
- fallback posicional para HTML legado;
- busca do formulário também em iframes;
- teste isolado `TESTAR_LOGIN_ROBO_SSW.bat`;
- diagnóstico de inputs sem gravar `value`;
- screenshots antes/depois/erro;
- o teste NÃO navega para a opção 036.

## Fluxo recomendado

1. aplicar o patch;
2. executar `TESTAR_LOGIN_ROBO_SSW.bat`;
3. somente se `LOGIN OK`, voltar ao Painel e testar a opção 036;
4. em falha, usar `robot_ssw/diagnostico_login/login_erro.png` e `login_campos_erro.json`.
