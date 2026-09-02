# Hotfix v0.3.0.9 — Watchdog por domínio (Robô x Import Engine)

## Problema observado
Uma execução mensal podia terminar o download corretamente e continuar aparecendo como `DOWNLOADED` enquanto o Import Engine trabalhava. O watchdog media o mesmo limite externo desde o início do robô e só observava `status.json` do robô. Assim, uma importação longa podia ser tratada como travamento do robô.

## Correção
- Timeout do robô permanece independente (`SSW_ROBOT_TIMEOUT_SECONDS`, padrão 900s).
- Após `DOWNLOADED` ou o primeiro progresso fresco do importador, o watchdog muda para o domínio `IMPORT`.
- O Import Engine recebe timeout próprio (`SSW_IMPORT_TIMEOUT_SECONDS`, padrão 3600s).
- O watchdog passa a ler `local_data/import_progress/run_<id>.json` e registra `IMPORT_PROGRESS` com fase, percentual e mensagem.
- Snapshot antigo de progresso é removido no início de uma nova tentativa.
- Escrita de progresso usa JSON atômico resiliente do v0.3.0.6 e continua best-effort.
- Falha inesperada após o download recebe código `IMPORT_ENGINE_ERROR`; antes do download, `ROBOT_UNEXPECTED`.
- Timeout de importação recebe código `IMPORT_HARD_TIMEOUT` e componente `import_engine`.

## Fluxo esperado
`ROBOT_STARTING → AUTHENTICATING → WAITING_DOWNLOAD → DOWNLOADED → IMPORT · Validação → IMPORT · Leitura/Normalização/Pré-carga/Comparação/Banco → IMPORT · Concluído → SUCCESS/WARNING`.

## Segurança
O diretório `robot_ssw/` homologado não é alterado por este hotfix.
