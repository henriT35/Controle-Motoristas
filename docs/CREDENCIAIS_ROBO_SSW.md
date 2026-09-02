# Credenciais locais do Robô SSW

A partir da versão `0.2.2-p4`, o Painel Motoristas possui um local único para configuração do login utilizado pelo robô SSW.

## Onde ficam

O arquivo real fica em:

```text
robot_ssw/credenciais.local.json
```

Ele é criado por:

```text
CONFIGURAR_CREDENCIAIS_SSW.bat
```

O usuário é solicitado normalmente e a senha é digitada de forma oculta no terminal. O arquivo é local e está listado no `.gitignore`.

## Fluxo

```text
CONFIGURAR_CREDENCIAIS_SSW.bat
        ↓
robot_ssw/credenciais.local.json
        ↓
painel_adapter.py
        ↓
variáveis de ambiente do processo do robô
        ↓
robô SSW real
```

As credenciais **não entram no `task.json`**, não são gravadas no banco do Painel e não fazem parte do contrato Sistema → Robô.

## Variáveis fornecidas ao robô

O adapter disponibiliza no processo do robô:

```text
SSW_USERNAME
SSW_PASSWORD
SSW_LOGIN_URL
ROBO_SSW_USERNAME
ROBO_SSW_PASSWORD
ROBO_SSW_LOGIN_URL
```

O código do robô pode usar qualquer um dos dois prefixos.

## Teste

Execute:

```text
TESTAR_CREDENCIAIS_SSW.bat
```

O teste informa apenas que o usuário/senha foram carregados. A senha nunca é impressa.

## Segurança

`credenciais.local.json` contém a senha localmente em texto legível pelo usuário do Windows. Não envie esse arquivo para terceiros, não o anexe ao Caderno de Bugs e não o inclua em releases. Uma evolução futura pode migrar esse segredo para o Gerenciador de Credenciais do Windows/DPAPI sem alterar o contrato do Painel.
