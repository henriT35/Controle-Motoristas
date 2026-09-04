# Integração do Robô SSW — implementação do Painel

Versão: **0.2.2-p3**

## O que foi implementado no Painel

O Painel passou a possuir um bridge real de execução para um robô Python externo. O sistema continua sendo o orquestrador e o robô continua sendo apenas executor.

Fluxo implementado:

```text
Usuário/agendamento
→ ImportRun QUEUED
→ DISPATCHED
→ processo local/Celery
→ Robô SSW
→ opção 036 / unidade BEL / Excel=S / período
→ arquivo .sswweb/.csv
→ validação
→ importador idempotente
→ banco atualizado
→ SUCCESS/WARNING/ERROR
```

### Contrato enviado ao robô

O Painel grava `task.json` por execução com:

- `execution_id`
- `report_type=ROMANEIOS_036`
- `ssw_option=036`
- `start_date`
- `end_date`
- `unit=BEL`
- `excel=S`
- `requested_by`
- `mode`
- `download_dir`
- `result_file`

Credenciais do SSW **não fazem parte do contrato**. Elas permanecem configuradas dentro do próprio robô.

### Retorno esperado

O bridge aceita `result.json` com, no mínimo:

```json
{
  "robot_status": "DOWNLOADED",
  "file_path": "C:/.../arquivo.sswweb"
}
```

Também aceita `message`, `messages`, `error_code` e `error_message`.

Se `file_path` não for informado, o Painel procura o `.sswweb`/`.csv` mais recente na pasta isolada daquela execução.

## Execução serial

Mesmo que uma importação histórica gere 12 meses, somente **uma sessão do robô é executada por vez**. Os outros meses ficam `QUEUED` e são liberados sequencialmente após sucesso/aviso da janela anterior.

Uma falha de login/selector/timeout interrompe a continuação automática da fila para evitar repetir o mesmo problema em vários meses.

## Modo local sem Docker

O modo padrão usa um processo Python separado:

```text
manage.py run_ssw_robot <run_id>
```

Isso evita bloquear a página web enquanto o Playwright está navegando no SSW.

Em produção pode ser usado:

```env
SSW_ROBOT_DISPATCH_MODE=celery
```

## Pasta do robô

Padrão:

```text
/robot_ssw/
```

O Painel tenta, nesta ordem:

1. `painel_adapter.py`
2. `integracao_painel.py`
3. `main.py`
4. `robo.py`
5. `robot.py`

Para uma CLI diferente, configure `SSW_ROBOT_COMMAND`.

## Adapter genérico

Foi incluído `robot_ssw/painel_adapter.py`. Ele pode chamar uma função do robô existente configurando:

```env
ROBO_PAINEL_MODULE=robo
ROBO_PAINEL_FUNCTION=executar_tarefa
```

A função pode receber o `task` inteiro ou parâmetros como `data_inicio`, `data_fim`, `download_dir`, `unidade`, `opcao` e `excel`.

## Configuração

```env
SSW_ROBOT_ENABLED=1
SSW_ROBOT_DIR=robot_ssw
SSW_ROBOT_DISPATCH_MODE=local_process
SSW_ROBOT_TIMEOUT_SECONDS=900
SSW_ROBOT_UNIT=BEL
SSW_ROBOT_OPTION=036
SSW_ROBOT_EXCEL=S
SSW_ROBOT_REPORT_TYPE=ROMANEIOS_036
```

Use `ATIVAR_ROBO_SSW.bat` para habilitar sem informar credenciais ao Painel.

Use `TESTAR_INTEGRACAO_ROBO_SSW.bat` para diagnóstico.

## Importador

O arquivo retornado pelo robô é processado pelo mesmo importador manual. O `ImportRun` original é reutilizado; não é criada uma execução artificial separada para o mesmo job.

Assim, histórico, contagens, steps e erros permanecem correlacionados à solicitação original.

## Estados visíveis

- `QUEUED` — aguardando
- `DISPATCHED` — enviado ao executor
- `RUNNING` — robô/importador trabalhando
- `SUCCESS`
- `WARNING`
- `ERROR`

Etapas registradas incluem Solicitação, Robô SSW, Download, Validação, Leitura e validação, Normalização e comparação, Processamento e Banco atualizado.

## Segurança

- Painel não envia usuário/senha no `task.json`.
- Logs passam por sanitização básica.
- stdout/stderr são limitados e não devem conter credenciais.
- arquivos ficam separados por `execution_id`.
- robô nunca grava diretamente nas tabelas operacionais.
