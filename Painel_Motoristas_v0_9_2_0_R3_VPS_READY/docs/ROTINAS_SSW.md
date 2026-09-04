# Central de Rotinas SSW — v0.9.2.0

## Core congelado

`robot_ssw/` é homologado e não deve ser alterado para UI, scheduler, fila, banco, importação, ranking, mapa, WhatsApp, Portal, Docker ou performance.

## Interface

A agenda é apresentada como uma Central de Rotinas única. Cada rotina possui:

- nome;
- ativa/inativa;
- tipo de período;
- período efetivo;
- frequência;
- janela diária;
- próxima execução;
- último resultado/status;
- Executar agora / Editar / Pausar / Excluir.

Tipos:

- **RECENT**: hoje/últimos N dias;
- **FIXED**: intervalo fixo, limitado ao dia atual quando a data final ainda está no futuro.

Períodos grandes continuam fatiados em janelas mensais antes de chegar ao core.

## Modal e responsividade

Formulários de criar/editar devem ficar acima da sidebar, centralizados, com `max-height`, scroll interno e fechamento previsível. Validar em 1920x1080, 1366x768, 1280x720, 1024, tablet e mobile.

## Scheduler Windows

`EXECUTAR_LOCAL.bat` e `EXECUTAR_ONLINE.bat` iniciam `manage.py run_ssw_scheduler --poll-seconds 30` por meio dos scripts PowerShell. Estado/heartbeat ficam fora do core homologado.

## Scheduler VPS

Celery Beat avalia a agenda; a execução real usa fila `ssw` e `robot-worker` dedicado. O lock/import lock impede concorrência de dois jobs SSW.

## Atualizar agora sem redirecionamento

O cabeçalho utiliza `data-ssw-update-now`. O JavaScript envia POST AJAX para `ssw_update_now`, recebe `run_id/status/progress_url`, permanece na tela e acompanha o job por polling. Ao terminar, recarrega a própria tela para refletir os novos dados.

## Resiliência

- heartbeat;
- reconciliação de run órfão;
- fila pausável após falha externa;
- retry controlado fora do core;
- logs/diagnóstico por execução;
- somente um robô SSW por vez.

## Banco/migrations

Scripts de boot não devem executar `makemigrations`. Eles validam migrations versionadas com `makemigrations --check --dry-run` e aplicam `migrate --fake-initial` quando apropriado à adoção de tabelas existentes.

A adoção de um banco real existente requer backup e homologação de migration antes de produção.

## Nota v0.9.2.0

O core/scheduler SSW não foi reinventado nesta versão. Após cada importação, a camada externa sincroniza eventos ROM13, obrigações de ressalva e reconcilia estados de comprovantes sem modificar `robot_ssw/`.
