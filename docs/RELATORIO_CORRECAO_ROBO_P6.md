# Correção Robô SSW — 0.2.2-p6

## Sintoma reproduzido
Ao clicar em Executar no SSW, uma janela preta do Python abria e fechava rapidamente. A interface permanecia como "Enviado ao robô" mesmo quando apenas `painel_adapter.py` estava instalado.

## Causa
O dispatcher considerava `painel_adapter.py` suficiente para iniciar uma execução. Porém o adapter é somente a ponte; sem um módulo/função do robô Playwright real ele termina com erro logo após ser iniciado. O processo local também era criado de forma que uma janela de console podia aparecer no Windows.

## Correções
- preflight obrigatório antes do despacho;
- `painel_adapter.py --check-ready` verifica credenciais + função real do robô sem abrir o navegador;
- adapter sozinho não é mais considerado robô funcional;
- falha de preflight vira `ImportRun=ERROR` imediatamente;
- a tela exibe a mensagem real da falha;
- o worker local usa `CREATE_NO_WINDOW` no Windows;
- o dispatcher não deixa a requisição web virar erro 500 durante falha de inicialização;
- diagnóstico mostra `Pronto para executar: SIM/NÃO`.

## Limite
Este patch corrige a integração/UX, mas não cria o Playwright real. Para navegar no SSW, a pasta `robot_ssw` ainda precisa conter o código real do robô ou um `SSW_ROBOT_COMMAND` válido.
