# Relatório de Testes — Integração Robô SSW — 0.2.2-p5

## Escopo
Bateria executada sobre o adapter/bridge disponível no pacote. O código do Playwright real do SSW não estava presente no ambiente de testes; portanto login/navegação/download reais no site SSW não foram declarados como homologados.

## Resultado antes da correção
14 cenários isolados do adapter: **10 aprovados / 4 falhos**.

Falhas encontradas:
1. retorno `status=ERROR` do robô podia ser convertido em `DOWNLOADED` se existisse um arquivo parcial;
2. funções do robô definidas somente com `**kwargs` não recebiam o contrato;
3. senha podia aparecer em `stdout` do robô;
4. senha podia aparecer em `error_message`/`traceback` do `result.json`.

## Correções p5
- respeita `ERROR/FAILED/FAILURE` informado pelo robô;
- `**kwargs` recebe aliases/campos do contrato;
- captura stdout/stderr Python do robô e sanitiza senha;
- sanitiza exception e traceback antes do `result.json`;
- valida campos mínimos do `task.json`;
- `ssw_robot_doctor` separa claramente `Adapter do Painel` de `Robô real detectado`;
- adicionado `TESTAR_ROBO_BATERIA.bat`.

## Critério de integração real
O diagnóstico deve apresentar `Robô real detectado: SIM`. Se aparecer apenas `Adapter do Painel: SIM` e `Robô real detectado: NÃO`, o Playwright real ainda não está instalado na pasta `robot_ssw`.
