# Relatório de Testes — Robô SSW p13

## Verificações executadas no ambiente de construção

### 1. Integridade do core
Resultado: **PASS**.

Os seis arquivos Python do core instalado no p13 foram comparados byte a byte com o pacote `robo_ssw_painel_motoristas_v1` fornecido. Todos permaneceram idênticos.

### 2. Teste contratual isolado do fluxo
Resultado: **PASS**.

`mock_contract_test.py` substitui apenas o transporte Playwright por objetos controlados e executa o `worker.py` original sem modificá-lo. Foi verificada a sequência:

```text
ROBOT_STARTING
→ AUTHENTICATING
→ clique role=link name=►
→ fill opção 036
→ press Enter
→ expect_popup
→ #t_excel=S
→ #t_unidade=BEL
→ #t_dt_ini=010826
→ #t_dt_fin=310826
→ REQUESTING_REPORT
→ WAITING_DOWNLOAD
→ expect_download
→ #btn_env_periodo.click()
→ DOWNLOADED
```

O teste também comprovou criação do arquivo e retorno de SHA-256.

### 3. Validação estática
Resultado: a executar no fechamento do ZIP com `compileall`.

### 4. Django runtime
Não executado no ambiente de construção por ausência do Django instalado. Foram incluídos testes `apps/ssw/tests_robot_p13.py` para executar no Windows com `TESTAR_SISTEMA.bat`/suite Django.

### 5. SSW real
Não executado neste ambiente. O p13 inclui testes progressivos que devem ser rodados no computador com acesso ao SSW:

- `TESTAR_LOGIN_ROBO_HOMOLOGADO.bat`;
- `TESTAR_OPCAO_036.bat`;
- `TESTAR_CONSULTA_036.bat`;
- `TESTAR_DOWNLOAD_036.bat`.

Nenhuma etapa real será marcada como aprovada sem evidência do Windows/SSW.
