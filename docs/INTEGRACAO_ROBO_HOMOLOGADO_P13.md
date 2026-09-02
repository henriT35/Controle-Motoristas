# Integração do Robô SSW Homologado — p13

## Objetivo
Integrar o executor já homologado ao Painel Motoristas sem reescrever o fluxo SSW.

## O que foi preservado
- Login original com IDs `1`, `2`, `3`, `4` e clique em `page.get_by_role("link", name="►")`.
- Menu com `fill("036")` seguido de `press("Enter")`.
- Abertura da 036 via `expect_popup()`.
- `#t_excel = S`.
- `#t_unidade = BEL`.
- Datas `#t_dt_ini/#t_dt_fin` em `DDMMAA`.
- Geração por `#btn_env_periodo.click()`.
- Captura do arquivo por `expect_download()`.
- Pasta isolada por `execution_id`.
- `status.json`, `result.json`, `robot.log`, evidências e SHA-256.
- Limite de 31 dias por job.

## O que foi adaptado
Somente:
- `build_robot_payload()`;
- carregamento seguro da API `run_job`;
- `status_callback` para `ImportRun/ImportStep`;
- preflight;
- dispatch local silencioso;
- transição `DOWNLOADED → Validação → Processamento → Banco atualizado`;
- serialização de janelas históricas;
- migração da configuração de credenciais para o formato do core original.

## Arquitetura

```text
Tela Importações
       ↓
queue_import()
       ↓
ImportRun QUEUED
       ↓
dispatch.py
       ↓
manage.py run_ssw_robot <id>
       ↓
robot_service.py
       ↓
robot_ssw.run_job(payload, callback)
       ↓
CORE HOMOLOGADO
       ↓
SSW 036
       ↓
DOWNLOADED
       ↓
robot_service.py
       ↓
import_ssw_delivery_file(existing_run=...)
       ↓
VALIDAÇÃO / PROCESSAMENTO / BANCO
       ↓
SUCCESS ou WARNING
```

## Segurança
O payload não contém empresa, CPF, usuário ou senha. O executor lê `robot_ssw/.env`. Logs do core passam pelo sanitizador original. O patch não inclui credenciais reais.

## Backup do executor experimental
Na aplicação do patch, a pasta `robot_ssw` anterior é copiada integralmente para:

```text
local_data/patch_backups/backup_robot_pre_p13_<timestamp>/robot_ssw/
```

Depois disso a pasta ativa é reconstruída somente com o core homologado + ferramentas p13.

## Aceitação
A integração só estará homologada após os testes reais, nesta ordem:
1. login;
2. opção 036;
3. preenchimento da consulta;
4. download 036;
5. execução ponta a ponta pela tela do Painel.
