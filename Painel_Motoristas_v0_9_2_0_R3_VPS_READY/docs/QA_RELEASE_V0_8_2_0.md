# QA release v0.8.2.0

## Checagens executáveis neste ambiente

- compilação estática de todos os arquivos Python;
- `node --check static/js/app.js`;
- testes isolados da configuração de rotinas: default 2h, upgrade do formato legado, clamp de período fixo até hoje, janela diária normal e atravessando meia-noite, próxima execução visual;
- comparação byte a byte do diretório `robot_ssw` contra v0.8.1.0;
- comparação estrutural do payload do patch aplicado sobre uma cópia limpa da v0.8.1.0;
- varredura do pacote para impedir `.env`, banco, sessão do WhatsApp, `node_modules`, `.venv` e caches Python.

## Não homologado aqui

Este ambiente não possui a stack Django/Windows completa nem acesso real ao SSW. Portanto não é válido afirmar execução real de PowerShell, browser SSW, Celery/Redis, boot da Hostinger ou renderização em monitores físicos. A homologação final deve ser feita no Windows do projeto e depois na VPS.

## Roteiro de homologação Windows

1. aplicar o patch sobre v0.8.1.0;
2. iniciar `EXECUTAR_ONLINE.bat`;
3. confirmar `Scheduler SSW : ativo` no console;
4. abrir Importações SSW e confirmar `SCHEDULER ONLINE`;
5. deixar a rotina padrão ativa e conferir criação do FAST dos últimos 2 dias;
6. criar uma rotina curta de teste, por exemplo 30 minutos, e validar o segundo ciclo;
7. disparar **Executar agora** com outro job ativo e confirmar fila sem Chromium concorrente;
8. abrir Dashboard em resoluções menores e conferir sidebar/conta;
9. abrir um período anual, usar slider/roda, **Ampliar**, `Esc` e **Todo período**.
