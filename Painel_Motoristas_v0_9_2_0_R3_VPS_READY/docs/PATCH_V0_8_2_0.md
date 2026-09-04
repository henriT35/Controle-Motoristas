# Patch v0.8.2.0 — UX, gráfico e rotinas automáticas SSW

Base obrigatória: **v0.8.1.0**.

## Causa do robô não iniciar sozinho no Windows

A configuração da v0.8.1.0 era lida por uma task agendada no Celery Beat. O Docker/VPS possuía serviço `beat`, mas os scripts `EXECUTAR_LOCAL.bat` e `EXECUTAR_ONLINE.bat` não iniciavam nenhum scheduler equivalente. O web server podia permanecer online por horas sem existir processo responsável por chamar a agenda.

A v0.8.2.0 adiciona um scheduler local persistente e faz os scripts de boot iniciarem/pararem esse processo junto com o Painel.

## Principais alterações

- navegação lateral com scroll próprio e conta sempre reservada no rodapé;
- compactação para monitores de pouca altura;
- gráfico de Evolução Operacional com slider, zoom e modo ampliado;
- múltiplas rotinas SSW com período, cadência e horário próprios;
- padrão novo: últimos 2 dias / 120 min / 05:00–23:30;
- execução imediata por rotina;
- heartbeat visível do scheduler;
- configuração antiga migrada de forma transparente;
- nenhuma alteração do core `robot_ssw`.

## Depois de aplicar

Inicie novamente por `EXECUTAR_LOCAL.bat` ou `EXECUTAR_ONLINE.bat`. Na tela **Importações SSW**, o selo `SCHEDULER ONLINE` deve aparecer em até cerca de 30–60 segundos. Uma instalação sem agenda anterior recebe a rotina padrão e a primeira execução fica apta imediatamente.

Se o selo continuar offline, consulte:

```text
local_data/logs/scheduler.err.log
local_data/logs/scheduler.out.log
```

No deploy Docker/VPS, mantenha o serviço `beat` ativo; ele executa a mesma decisão de agenda.
