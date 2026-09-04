# Robô SSW — Patch p9 — Login operacional

## Causa do erro `LOGIN_SELECTOR`

O robô v1.1 tratava o login como `Usuário + Senha`. A tela operacional atual do SSW utiliza quatro dados: **Domínio, CPF, Usuário e Senha**. Como o HTML legado nem sempre associa o texto visível a `<label for=...>`, procurar somente um seletor de usuário podia falhar mesmo com a página correta aberta.

## Correções

- credenciais locais agora incluem `domain`, `cpf`, `username`, `password` e `login_url`;
- adapter exporta `SSW_DOMAIN`, `SSW_CPF`, `SSW_USERNAME`, `SSW_PASSWORD` somente ao processo do robô;
- login procura campos por label/name/id/placeholder;
- fallback por ordem DOM oficial: Domínio → CPF → Usuário → Senha;
- botão de login passa a aceitar também `input[type=image]`;
- diagnóstico informa apenas se Domínio/CPF estão configurados, sem mostrar seus valores;
- em erro de seletor o robô preserva a screenshot em `diagnostico/`.

## Passos depois do patch

1. `APLICAR_PATCH.bat`
2. `CONFIGURAR_CREDENCIAIS_SSW.bat`
3. informar Domínio, CPF, Usuário, Senha e URL de login
4. `DIAGNOSTICAR_ROBO_SSW.bat`
5. solicitar uma importação curta pelo Painel

## Segurança

`credenciais.local.json` continua local e não é colocado no `task.json` nem no banco do Painel.
