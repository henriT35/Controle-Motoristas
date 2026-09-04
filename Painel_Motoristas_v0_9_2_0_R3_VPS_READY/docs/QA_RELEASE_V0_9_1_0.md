# QA release — v0.9.1.0

**Tipo:** estabilização + homologação + performance + acabamento  
**Data:** 03/09/2026

## 1. Status

Esta entrega é uma **candidata de release v0.9.1.0** com QA portátil/estático concluído no ambiente disponível e com **HOMOLOGAÇÃO EXTERNA PENDENTE** para tudo que depende de Django instalado, banco real, SSW real, dispositivo WhatsApp, browser/viewport real ou VPS.

Há uma ressalva de linhagem: foi solicitada a v0.9.0.0 como baseline obrigatória, porém o material recebido não continha um ZIP funcional oficial v0.9.0.0. A origem funcional efetivamente disponível era a árvore completa v0.8.2.0 acompanhada do handoff/documentação v0.9.0.0. O patch declara essa origem de forma explícita.

## 2. QA realmente executado — PASS

| Verificação | Resultado real |
|---|---|
| `python -m compileall -q apps config scripts manage.py` | PASS |
| QA portátil | PASS — 206 arquivos Python; 6/6 invariantes |
| migrations v0.9.1.0 — contrato estático | PASS |
| fórmula performance/Ranking V3 | PASS — cenário V3 de QA = 94,5 |
| performance/importador — contrato estático | PASS |
| robot adapter + core homologado | PASS — 6/6 hashes do manifesto interno |
| mock contrato SSW 036 | PASS — login mock → 036 → S/BEL/período → download |
| decorators SSW | PASS |
| templates/rotas | PASS — 69 nomes conhecidos, 0 referência estática órfã |
| contrato v0.9.1.0 | PASS |
| regressões temporais permanentes — contrato estático | PASS — ROM85/ROM34/código 13/CTRC/60/53/91 presentes |
| VPS — contrato estático | PASS |
| WhatsApp Baileys — contrato estático | PASS |
| telefone BR com/sem 9 — contrato estático | PASS |
| `node --check static/js/app.js` | PASS |
| `node --check whatsapp_bridge/server.mjs` | PASS |
| `bash -n` scripts Docker/VPS | PASS — 7 scripts |
| integridade `robot_ssw/` contra origem fornecida | PASS — 17/17 arquivos, 0 divergências |

O teste temporal estático confirma que a suíte permanente mantém casos para:

- ROM34 vencendo CTRC34 repetido na escolha da tentativa/origem;
- 60/53/91 pós-retenção indo para `VERIFICAR`;
- `VERIFICAR` só virando recuperado após evidência conclusiva de entrega;
- ROM34 sem data não usando instante da importação;
- evento ROM posterior não migrando tentativa antiga para outro dia;
- CTRC consolidado não inferindo rota;
- múltiplos romaneios/tentativas do mesmo CT-e;
- código 13 encerrando a tentativa antiga antes de uma nova saída;
- reconstrução histórica somente quando o casamento é único e determinístico.

**Importante:** presença/contrato estático de testes não substitui a execução `django.test`; a execução real desses testes ficou pendente porque Django não está instalado neste ambiente.

## 2.1. Correção após execução real no Windows

Na primeira execução do `EXECUTAR_ONLINE.bat` da candidata v0.9.1.0, o ambiente real com Django detectou divergência de estado e propôs migrations contendo **somente `RenameIndex`** nos apps `bugs`, `drivers`, `messaging`, `operations`, `proofs`, `reports` e `ssw`. O executor bloqueou corretamente a inicialização em vez de criar migrations automaticamente.

A correção aplicada nesta revisão mantém as migrations existentes e passa a declarar nos `models.Index(...)` os nomes explícitos já gravados nas migrations versionadas. Isso evita renames cosméticos, não altera a lógica dos dados e não requer renomear índices já existentes. Foi acrescentado um teste estático de regressão que exige correspondência explícita desses nomes.

Como este ambiente de empacotamento continua sem Django instalado, o `makemigrations --check --dry-run` real **deve ser reexecutado no Windows** com este pacote corrigido. O resultado esperado é `No changes detected`.

## 2.2. Hotfix após runtime real do Dashboard no Windows

Após a correção dos nomes de índices, a execução real avançou até o Waitress (`Serving on http://127.0.0.1:8000`), confirmando que o bloqueio anterior de migrations deixou de impedir o boot. Ao acessar `/dashboard/`, o runtime registrou:

`NameError: name 'versioned_key' is not defined` em `apps/core/services.py`, dentro de `operational_manifest_evidence_map()`.

A inspeção mostrou que o mesmo módulo também usava `cache.get/cache.set` sem importar `cache`. A candidata foi corrigida com os imports explícitos:

- `from django.core.cache import cache`;
- `from .cache import versioned_key`.

Foi ampliado `scripts/qa/test_v091_contract_static.py` para exigir ambos os imports e o uso da chave versionada. `compileall` e os contratos portáteis passaram novamente.

**Reteste externo ainda necessário:** abrir `/dashboard/` nesta build corrigida e navegar Dashboard → Operação → Ranking para confirmar que não existe outro erro de runtime encoberto pela ausência de Django no ambiente de empacotamento.

## 3. Comandos tentados, mas indisponíveis neste ambiente

### Django

Os comandos abaixo foram realmente tentados e falharam antes de iniciar a aplicação porque o Python disponível não possui Django:

- `python manage.py check` → `ModuleNotFoundError: No module named 'django'`;
- `python manage.py makemigrations --check --dry-run` → mesmo impedimento;
- `python manage.py migrate --plan` → mesmo impedimento.

A descoberta de `unittest` também não pôde carregar o projeto porque `celery` não está instalado.

Uma tentativa anterior de instalar dependências não pôde prosseguir por indisponibilidade de rede/DNS no ambiente de execução. Não classificamos isso como PASS.

### Docker/VPS

`docker compose config` não pôde ser executado porque o binário `docker` não está instalado neste ambiente. A estrutura foi validada apenas pelo QA estático.

### PowerShell/Windows

`pwsh` não está disponível; os scripts PowerShell não tiveram parsing real neste host. A lógica foi inspecionada e os contratos estáticos passaram.

### SSW real

`robot_ssw/contract_test.py` real não foi executado porque as credenciais SSW não foram fornecidas ao ambiente. O mock P13/036 passou.

## 4. QA com dados reais SSW

O handoff cita um ZIP privado com 10 relatórios reais de janeiro a 02/09/2026. **Esse ZIP não está presente no pacote recebido nem no ambiente desta rodada.** Portanto não foi possível reimportar esses relatórios e não foi inventado resultado.

Os testes de regressão permanentes foram preservados/expandidos para os casos descobertos nesses dados, mas a reexecução com os arquivos reais permanece externa.

## 5. Performance

Foram implementados/instrumentados:

- logs `PERF ...` por componente/tela;
- cache operacional versionado;
- invalidação centralizada;
- cache de KPIs e oportunidades;
- redução de consultas repetidas na Central WhatsApp;
- compartilhamento de métricas de ranking;
- gráfico pesado do Dashboard carregável separadamente;
- uso de Redis na VPS e fallback de cache local no Windows.

**Não há tempos HTTP frio/quente válidos nesta release**, porque não havia Django+banco executável neste ambiente. Nenhum número foi fabricado.

Homologação externa deve medir, no banco real e com volume anual:

1. Dashboard;
2. Operação de Hoje;
3. Ranking;
4. Motoristas;
5. Comprovantes Retidos;
6. Entregas Gerais/WhatsApp se apresentarem latência.

Para cada tela: cache frio, cache quente, número de queries, volume de dados e tempos `PERF`.

## 6. UI

A estrutura/CSS/JS foi revisada para modal das Rotinas, QR compacto, Central WhatsApp única, ranking, Portal, sidebar e gráfico. Entretanto não houve navegador gráfico real neste ambiente.

**HOMOLOGAÇÃO EXTERNA PENDENTE** em:

- 1920×1080;
- 1366×768;
- 1280×720;
- 1024 px;
- tablet;
- mobile 360–430 px;
- zoom/pan/ESC/tooltip do gráfico;
- câmera/galeria/PDF no Portal;
- QR e reconexão Baileys reais.

## 7. Banco/migrations

O QA estático confirma migrations formais e que boot Windows/Docker não executa `makemigrations` criativo. Porém a adoção real precisa de:

1. backup do banco;
2. cópia de homologação;
3. `manage.py check`;
4. `makemigrations --check --dry-run`;
5. `migrate --plan`;
6. `migrate` em SQLite de teste e PostgreSQL de homologação;
7. conferência de dados e rollback/backup.

## 8. Segurança/integridade

Antes do empacotamento final devem permanecer ausentes: `.env` real, credenciais SSW locais, bancos, logs reais, uploads/media reais, sessão Baileys, `node_modules`, `.venv` e caches Python. Arquivos `.env*.example` são placeholders documentais.

Redirecionamentos POST controlados por usuário foram endurecidos com validação de host; a solicitação pública de novo link usa resposta genérica e throttle de curta duração; links do Portal respeitam `PANEL_PUBLIC_BASE_URL`.

## 9. Patch — QA de aplicação

O patch foi calculado a partir da origem **efetivamente disponível**, com manifesto de hashes e patcher defensivo. Um dry-run foi executado sobre uma cópia limpa/canônica da origem recebida.

Resultado do dry-run de empacotamento:

- origem canônica: 482 arquivos;
- baseline v0.9.1.0 canônica: 507 arquivos;
- arquivos adicionados pelo patch: 25;
- arquivos modificados: 62;
- arquivos removidos: 0;
- `robot_ssw/` dentro do payload: **0 arquivos**;
- aplicação do patcher: **PASS**;
- diferença de caminhos após aplicar patch versus baseline v0.9.1.0: **0**;
- diferença de SHA-256/conteúdo após aplicar patch versus baseline v0.9.1.0: **0**.

Depois da consolidação deste relatório, o pacote final repete o dry-run; qualquer divergência invalida a entrega.

## 10. HOMOLOGAÇÃO EXTERNA PENDENTE

- Django `check`;
- `makemigrations --check --dry-run` real;
- migrations SQLite e PostgreSQL;
- suíte Django completa;
- regressão com os 10 relatórios SSW reais;
- benchmarks cache frio/quente;
- SSW 036 real;
- scheduler Windows real;
- Celery/Redis/robot-worker na VPS;
- WhatsApp/Baileys real e persistência após restart;
- UI nas resoluções alvo;
- Portal em celular real;
- geocoder/mapa com rede real;
- `docker compose config/up` e reboot da VPS;
- rebase/comparação se aparecer uma baseline funcional oficial v0.9.0.0 diferente da origem recebida.
