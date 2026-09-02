# Hotfix p13.4 — Credenciais do Robô SSW Homologado

## Causa

O projeto completo p13.3 continha dois problemas no fluxo de credenciais:

1. `CONFIGURAR_CREDENCIAIS_SSW.bat` chamava `scripts/windows/configure-homologated-credentials.ps1`, que não estava no pacote.
2. Os scripts antigos gravavam `robot_ssw/credenciais.local.json`, enquanto o core homologado p13 lê `robot_ssw/.env` (`SSW_EMPRESA`, `SSW_CPF`, `SSW_USUARIO`, `SSW_SENHA`, `SSW_URL`).

Por isso era possível preencher credenciais e o robô continuar usando valores antigos ou considerar a configuração incompleta.

## Correção

O p13.4 unifica toda a configuração no arquivo oficial do core homologado:

```text
robot_ssw/.env
```

Os scripts `CONFIGURAR_CREDENCIAIS_SSW.bat`, `VERIFICAR_CREDENCIAIS_SSW.bat` e `MIGRAR_CREDENCIAIS_SSW_P13.bat` agora usam `scripts/robot_credentials.py`.

O configurador:

- preserva valores existentes ao pressionar Enter;
- aceita senha com caracteres especiais;
- grava UTF-8 sem BOM;
- fixa opção `036` e unidade `BEL`;
- usa a pasta `imports/inbox` do próprio projeto;
- consegue aproveitar o antigo `credenciais.local.json` como fonte de migração;
- não imprime senha ou CPF completo durante a verificação.

## Uso

1. `APLICAR_HOTFIX_P13_4.bat`
2. `CONFIGURAR_CREDENCIAIS_SSW.bat`
3. `VERIFICAR_CREDENCIAIS_SSW.bat`
4. `TESTAR_LOGIN_ROBO_HOMOLOGADO.bat`

O arquivo `.env` contém segredo e não deve ser enviado nem versionado.
