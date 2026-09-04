# Rotinas SSW — v0.8.2.0

## Objetivo

A agenda do robô deixa de depender de um único intervalo global. O Painel pode manter várias rotinas independentes e o mesmo mecanismo funciona no Windows e na VPS.

## Tipos de rotina

### Janela recente (`RECENT`)

Indicada para acompanhar a operação corrente. O período é recalculado em cada execução até o dia atual.

Exemplo recomendado para rotas diárias:

- nome: `Rotas do dia`;
- últimos dias: `2`;
- intervalo: `120` minutos;
- ativa de `05:00` até `23:30`.

Esse modelo captura complementos do SSW durante o dia sem depender de um período fixo.

### Período fixo (`FIXED`)

Usado para reconsultar uma faixa determinada, por exemplo `01/01/2026` até `31/12/2026`. Enquanto a data final estiver no futuro, o scheduler consulta somente até a data atual. O orquestrador divide intervalos grandes mês a mês antes de colocar na fila.

Não existem vários navegadores concorrentes: o dispatcher SSW só despacha um job por vez. As demais janelas aguardam em `QUEUED`.

## Regras de execução

Uma rotina só dispara automaticamente quando:

1. a automação geral está ativa;
2. a rotina está ativa;
3. o horário atual está dentro da janela diária;
4. o período já é executável;
5. o ciclo anterior da própria rotina terminou;
6. o intervalo configurado venceu;
7. a fila SSW não está pausada por segurança.

O botão **Executar agora** ignora a espera do intervalo, mas continua usando a mesma fila, deduplicação e trava do robô.

## Windows

`EXECUTAR_LOCAL.bat` e `EXECUTAR_ONLINE.bat` iniciam também:

```text
python manage.py run_ssw_scheduler --poll-seconds 30
```

Arquivos operacionais:

```text
local_data/scheduler.pid
local_data/logs/scheduler.out.log
local_data/logs/scheduler.err.log
local_data/ssw_scheduler_state.json
```

`PARAR_LOCAL.bat` e `PARAR_ONLINE.bat` encerram o scheduler junto com o servidor.

## VPS

O container `beat` consulta as rotinas a cada minuto. Não é necessário iniciar o management command do Windows dentro do Docker.

## Persistência

As rotinas ficam em:

```text
local_data/ssw_schedule.json
```

Na VPS, `local_data` é volume persistente. `git pull` e rebuild dos containers não apagam a agenda.

## Compatibilidade com v0.8.1.0

Se existir o formato antigo:

```json
{"enabled": true, "interval_minutes": 60}
```

a primeira leitura o converte em uma rotina `RECENT` preservando o intervalo anterior. Não há migration de banco para a agenda.
