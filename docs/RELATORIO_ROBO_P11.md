# Painel Motoristas — Patch p11 — Credenciais do login SSW

## Causa
O teste p10 confirmou que o robô correto estava carregado (`1.2.0-p10`), porém o adapter encontrou o arquivo local de credenciais sem as chaves `domain` e `cpf`. O patch p10 não carregava junto o configurador novo introduzido no p9. Em instalações que ainda tinham o configurador antigo, usuário/senha/URL eram salvos, mas domínio/CPF não eram persistidos.

## Correção
- `CONFIGURAR_CREDENCIAIS_SSW.bat` atualizado e incluído no próprio patch.
- Migração dos valores existentes de usuário/senha/URL.
- Domínio e CPF obrigatórios.
- Gravação UTF-8 sem BOM.
- Leitura de volta e validação imediatamente após salvar.
- `VERIFICAR_CREDENCIAIS_SSW.bat` mostra caminho e presença das chaves sem exibir valores sensíveis.
- Adapter passa a aceitar BOM no JSON e informa o caminho/chaves encontradas em caso de arquivo incompleto.

## Ordem de teste
1. Aplicar p11.
2. Executar `CONFIGURAR_CREDENCIAIS_SSW.bat`.
3. Executar `VERIFICAR_CREDENCIAIS_SSW.bat` — todos os cinco campos devem mostrar SIM.
4. Executar `TESTAR_LOGIN_ROBO_SSW.bat`.
