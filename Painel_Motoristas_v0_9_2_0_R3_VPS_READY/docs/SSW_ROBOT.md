# Robô SSW — executor homologado integrado ao Painel

## Regra-mãe
**Painel Motoristas = ORQUESTRADOR. Robô SSW = EXECUTOR.**

A partir da `0.2.2-p13`, o executor principal volta a ser o pacote homologado original, exposto pela API:

```python
from robot_ssw import run_job
resultado = run_job(payload, status_callback=callback)
```

Os executores experimentais dos patches p10/p12 não participam mais do caminho de produção. O instalador p13 faz backup da pasta anterior em `local_data/patch_backups/backup_robot_pre_p13_*` e instala um diretório `robot_ssw/` limpo.

## Core preservado
Os seguintes arquivos são copiados byte a byte do pacote homologado original e possuem manifesto `robot_ssw/HOMOLOGATED_CORE.sha256`:

- `robot_ssw/robot_ssw/__init__.py`
- `robot_ssw/robot_ssw/config.py`
- `robot_ssw/robot_ssw/io_utils.py`
- `robot_ssw/robot_ssw/models.py`
- `robot_ssw/robot_ssw/worker.py`
- `robot_ssw/robot_ssw/cli.py`

O bridge do Painel não altera esses arquivos.

## Fluxo SSW preservado

```text
login
→ IDs 1/2/3/4
→ link ►
→ campo da opção = 036
→ Enter
→ expect_popup()
→ #t_excel = S
→ #t_unidade = BEL
→ #t_dt_ini / #t_dt_fin em DDMMAA
→ expect_download()
→ #btn_env_periodo.click()
→ relatorio_036.<extensão>
→ SHA-256
→ DOWNLOADED
```

Não usar no executor principal heurísticas de proximidade, TAB+ENTER, descoberta de submit ou varredura de Downloads.

## Contrato Painel → Robô

```json
{
  "execution_id": "SSW-20260831-00125",
  "start_date": "2026-08-01",
  "end_date": "2026-08-31",
  "mode": "HISTORY",
  "requested_by": "admin",
  "report_type": "ROMANEIOS_036",
  "unit": "BEL",
  "download_dir": ".../imports/inbox/SSW-20260831-00125"
}
```

Credenciais nunca entram no payload.

## Estados
Robô:

`ROBOT_STARTING → AUTHENTICATING → REQUESTING_REPORT → WAITING_DOWNLOAD → DOWNLOADED`

ou `ERROR`.

Painel, somente após `DOWNLOADED`:

`Validação → Processamento → Banco atualizado → SUCCESS/WARNING`

**DOWNLOADED não é SUCCESS.**

## Callback
O `status_callback` recebe um `RobotEvent` e só pode atualizar:

- `ImportRun`;
- `ImportStep`;
- mensagem/progresso;
- timestamps.

Nunca deve alterar CT-es, rotas, clientes, motoristas, comprovantes ou score.

## Credenciais
O core homologado lê `robot_ssw/.env`:

```text
SSW_URL=...
SSW_EMPRESA=...
SSW_CPF=...
SSW_USUARIO=...
SSW_SENHA=...
SSW_UNIT=BEL
SSW_OPTION=036
```

O p13 migra automaticamente o antigo `credenciais.local.json` quando possível. O JSON legado é removido da pasta ativa após migração completa; a cópia anterior permanece no backup do patch.

## Execução local
O Painel continua abrindo um processo silencioso:

```text
python manage.py run_ssw_robot <run_id>
```

Esse management command chama a API `run_job()` do pacote homologado. O código Playwright não é duplicado dentro do Django.

## Histórico
O Painel quebra períodos longos em janelas mensais. O robô rejeita job acima de 31 dias. Apenas uma janela é executada por vez.

## Diagnóstico p13

```text
PREPARAR_ROBO_HOMOLOGADO.bat
TESTAR_CORE_ROBO_HOMOLOGADO.bat
TESTAR_INTEGRACAO_ROBO_SSW.bat
TESTAR_LOGIN_ROBO_HOMOLOGADO.bat
TESTAR_OPCAO_036.bat
TESTAR_CONSULTA_036.bat
TESTAR_DOWNLOAD_036.bat
```

Os quatro últimos testes reais devem ser executados em sequência antes da homologação ponta a ponta pelo Painel.

## v0.8.0.0 — execução na VPS

O core homologado não foi alterado. Na VPS ele é executado por `robot-worker`, um worker Celery exclusivo com Playwright/Chromium Linux e concorrência 1. O web/beat despacha `apps.ssw.tasks.run_robot_import` para a fila `ssw`. Credenciais são injetadas pelo `.env` da VPS e materializadas apenas dentro do container em `/app/robot_ssw/.env`.

A frequência automática fica fora do core do robô. Celery Beat consulta `local_data/ssw_schedule.json`; o botão **Atualizar agora** usa o mesmo `queue_import`/lock.
