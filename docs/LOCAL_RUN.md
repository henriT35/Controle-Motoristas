# Execução local sem Docker — V0.2.2

## Abrir o sistema
1. Instale Python 3.10+ (`INSTALAR_PYTHON.bat` pode usar winget).
2. Execute `EXECUTAR_LOCAL.bat`.
3. Na primeira execução o script cria `.venv`, instala/verifica dependências, aplica migrations e cria o administrador.
4. O navegador abre em `http://127.0.0.1:8000/login/`.

Credenciais iniciais de desenvolvimento:

- usuário: `admin`
- senha: `Painel@2026!`

## Banco
O modo local rápido usa SQLite em `local_data/painel_motoristas.sqlite3`.

O banco oficial/alvo é PostgreSQL. Para PostgreSQL instalado diretamente no Windows, execute `CONFIGURAR_POSTGRESQL_LOCAL.bat`, informe a conexão e rode `EXECUTAR_LOCAL.bat` novamente.

## Importar SSW
- Um arquivo: `IMPORTAR_RELATORIO_SSW.bat`.
- Vários meses em uma pasta: `IMPORTAR_LOTE_SSW.bat`.
- Vários arquivos pelo navegador: menu **Importações SSW**.

## Testar
`TESTAR_SISTEMA.bat` executa check + suíte Django.

## Capturar as telas
Com o servidor aberto, `CAPTURAR_TELAS.bat` grava as 12 telas em `docs/homologacao/v0_2_2/`.

## Parar
`PARAR_LOCAL.bat`.

## Logs
`VER_LOGS_LOCAL.bat`.

## Reset do banco rápido
`RESETAR_BANCO_LOCAL.bat` apaga somente o SQLite local após confirmação. O atalho não apaga PostgreSQL automaticamente.
