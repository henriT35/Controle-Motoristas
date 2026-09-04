# CONTEXTO MESTRE — PAINEL MOTORISTAS v0.9.1.0

**Projeto:** Controle dos Motoristas  
**Versão do pacote:** v0.9.1.0  
**Data:** 03/09/2026  
**Repositório:** `https://github.com/henriT35/Controle-Motoristas.git`

> Leia este arquivo, `docs/REGRAS_PARA_PROXIMO_AGENTE.md`, `docs/REGRAS_IMUTAVEIS.md`, `docs/PROCESSO_DE_ATUALIZACAO.md` e `docs/QA_RELEASE_V0_9_1_0.md` antes de alterar o projeto.

## 1. Aviso crítico de linhagem

A rodada v0.9.1.0 foi solicitada com baseline obrigatória v0.9.0.0. O pacote recebido, entretanto, **não continha uma baseline funcional oficial v0.9.0.0**. A última baseline funcional declarada e empacotada era v0.8.2.0, acompanhada de handoff/prompt/documentação da v0.9.0.0.

A árvore efetivamente usada nesta entrega foi:

`Painel_Motoristas_v0_8_2_0_BASELINE_COMPLETA_HANDOFF_v0_9_0_0`

Por isso:

- o ZIP v0.9.1.0 é uma **candidata à homologação**;
- o PATCH registra a árvore real de origem e seu hash de inventário;
- se surgir uma baseline funcional oficial v0.9.0.0 diferente, é obrigatório rebasear/comparar antes de produção;
- nunca fingir que o patch foi testado contra um artefato que não foi fornecido.

## 2. Objetivo do sistema

Painel web operacional/executivo para acompanhar motoristas, romaneios, CT-es, tentativas de entrega, ocorrências SSW, comprovantes retidos, recuperações, retiradas exatas, oportunidades regionais, clientes, mapa, WhatsApp e automações SSW.

Filosofia: **rápido, simples, operacional, auditável e explicável**. Interface: **Resumo → Clique → Detalhe**.

## 3. Stack

- Python / Django server-rendered;
- SQLite para local/homologação simples;
- PostgreSQL em produção;
- Redis + Celery/Celery Beat na VPS;
- Playwright/Chromium dentro do core homologado SSW opção 036;
- Node.js + Baileys para WhatsApp;
- Nginx + Gunicorn em Docker na VPS;
- Windows PowerShell + Waitress e Cloudflare Quick Tunnel no modo online temporário.

## 4. Estrutura principal

```text
apps/
  audit/       auditoria
  bugs/        caderno de bugs
  clients/     clientes/endereços
  core/        regras temporais, cache, performance, settings, métricas
  dashboard/   dashboard executivo
  drivers/     motoristas, Ranking V3, Portal
  messaging/   Central WhatsApp e fila Django
  operations/  operação diária, CT-es, mapa, oportunidades
  proofs/      retenções, recuperações, validação
  reports/     relatórios
  ssw/         orquestração/importação/scheduler ao redor do robô
robot_ssw/      CORE HOMOLOGADO CONGELADO
whatsapp_bridge/ serviço Node/Baileys
templates/      HTML server-rendered
static/         CSS/JS
scripts/windows scripts locais
scripts/docker  entrypoints
scripts/qa      QA portátil/estático
deploy/vps      automação VPS
docs/           documentação
```

## 4.1. Hotfix runtime confirmado no Windows

Durante a primeira homologação real da candidata v0.9.1.0, o Dashboard retornou HTTP 500 com `NameError: versioned_key is not defined` em `apps/core/services.py`. A otimização de cache já chamava `versioned_key()` e `cache.get/cache.set`, mas os imports haviam ficado ausentes. A build corrente corrige os dois imports e acrescenta regressão estática. `robot_ssw/`, models, migrations e regras temporais não foram alterados por esse hotfix. O próximo agente não deve remover esses imports.

## 5. Parte congelada

### `robot_ssw/`

Não alterar para corrigir UI, scheduler, fila, banco, importação, ranking, mapa, WhatsApp, Portal, Docker ou performance.

Nesta rodada, a comparação integral com a árvore de origem deu 17/17 arquivos com caminhos e bytes idênticos, depois de excluir artefatos `__pycache__` do QA. O manifesto homologado interno também valida 6/6 arquivos centrais.

Se for inevitável alterar o core: parar a promoção da release e re-homologar opção 036 ponta a ponta.

## 6. Regras temporais imutáveis

- Unidade operacional é a **tentativa/romaneio**, não o CT-e consolidado.
- ROM85 `SAIDA PARA ENTREGA` é a evidência preferencial de execução.
- Sem ROM85 datado, outro fato ROM datado pode inferir data operacional.
- Histórico sem `DATA OCORR ROM` só pode ser reconstruído com casamento determinístico ROM↔CTRC sem ambiguidade entre tentativas.
- ROM13 `ENTREGA PREJUDICADA PELO HORÁRIO` encerra aquela tentativa.
- Nova saída/romaneio = nova tentativa; outro motorista = motorista daquela nova tentativa.
- CTRC consolidado não promove todos os romaneios históricos do CT-e.
- Data de importação e data de emissão não inventam rota.

## 7. Retenção e recuperação

- ROM34 é a evidência principal da origem da retenção.
- CTRC34 é fallback quando não existe ROM34 adequado.
- `original_driver` + `original_manifest` apontam para a tentativa que originou a retenção.
- `recovery_driver` é independente e só deve apontar para quem realmente recuperou.
- Aprovação de submissão no Portal define `recovery_driver = submission.driver`.
- Nunca sobrescrever `original_driver` ao validar recuperação.
- 60 `DOCUMENTOS`, 53 `AVARIA`, 91 `INDENIZAÇÃO` e outros estados não conclusivos pós-retenção devem ficar `VERIFICAR`, salvo evidência conclusiva de entrega/recuperação.

## 8. Ranking V3

Uma única Nota Geral 0–100.

Pesos padrão:

- comprovantes 50%;
- qualidade operacional 35%;
- regularidade 15%.

Campos em `SystemSettings` permitem calibragem. Produtividade (CT-es, toneladas, frete, volumes) é estatística e não entra automaticamente na nota.

Eventos negativos são normalizados para uma causa principal por tentativa. Um ROM13 não pode ser penalizado três vezes por dimensões derivadas do mesmo fato.

Bônus padrão:

- recuperação exata aprovada: +0,30;
- ouro aprovado: +0,90;
- teto: +5,00.

A gestão pode configurar descrição do Top 3. O sistema apenas exibe; prêmio real é externo.

Código:

- `apps/core/performance.py`;
- `apps/core/services.py`;
- `apps/core/models.py`;
- `templates/drivers/index.html`.

## 9. Portal Web do Motorista

Tudo é web. Token individual em `DriverPortalAccess`.

Navegação mobile: Início / Comprovantes / Oportunidades / Ranking / Perfil.

Topo mostra posição, nota e diferença para posição superior quando aplicável.

### Novo link

Formulário público cria `DriverPortalAccessRequest` pendente, com resposta genérica e throttle leve. Coordenador aprova/rejeita. Somente aprovação regenera token. Opcionalmente enfileira mensagem WhatsApp.

Nunca gerar token automaticamente a partir do pedido público.

### Retenção

`ProofRetention` guarda motorista, romaneio, data, foto/PDF de ressalva e observação, sem trocar a origem do `RetainedProof`.

### Retirada exata

- RETIREI → evidência → pendente de validação;
- AINDA NÃO LIBERADO → neutro;
- NÃO FOI POSSÍVEL TENTAR → justificativa/auditoria.

### Ouro

Oportunidade regional é opcional. Ignorar/tentar sem sucesso/não liberado = neutro. Recuperação aprovada = bônus maior.

### Projeção

O Portal exibe nota/posição projetadas considerando o ranking atual. Não altera resultado oficial antes da validação.

## 10. Operação de Hoje

Cada rota deve mostrar diretamente:

- número de retiradas exatas;
- número de oportunidades de ouro.

Ambos clicáveis. Não esconder em múltiplos níveis de navegação.

## 11. WhatsApp

Fluxo oficial: **Django → fila `WhatsAppMessage` → Node.js/Baileys → WhatsApp**.

Não voltar para Chrome/Edge/Playwright/CDP como login.

Central tem uma lista única por motorista com cadastro, telefone, Portal, operação, comunicação e problemas.

A busca da última mensagem por motorista usa `Subquery`, evitando materializar todo o histórico.

Telefone BR testa candidatos com e sem o nono dígito quando necessário.

Sessão: `local_data/whatsapp/baileys_auth/` e volume persistente na VPS.

QR: card único compacto com status, QR, instruções, erro e ações.

Links enviados respeitam `PANEL_PUBLIC_BASE_URL` quando configurado.

## 12. SSW / opção 036

Parâmetros conhecidos:

- unidade `BEL`;
- Excel `S`;
- período fornecido pelo Painel/scheduler;
- download retornado ao importador.

Central de Rotinas: janela recente ou período fixo, frequência, janela diária, próxima execução, heartbeat e ações.

Windows: `run_ssw_scheduler --poll-seconds 30` acompanha o servidor local.

VPS: Celery Beat + fila `ssw` + `robot-worker`. Lock externo impede mais de um robô por vez.

“Atualizar agora” é AJAX/fetch: permanece na tela, acompanha progresso e recarrega apenas a tela atual ao concluir.

## 13. Cache e performance

`apps/core/cache.py` usa um namespace versionado. Qualquer fato operacional relevante incrementa a versão. Chaves antigas expiram sem serem reutilizadas.

Invalidação cobre Driver, CT-e, Manifest, movimentos, ocorrências, RetainedProof, submissions, ProofRetention, ProofPickupAttempt, ImportRun e SystemSettings. Também limpa o cache não-versionado do último sync exibido no cabeçalho.

RedisCache é usado quando `DB_MODE=postgres` e existe `REDIS_URL`. Fallback Windows/local: LocMemCache.

Dashboard:

- KPIs têm cache versionado por período;
- ranking oficial reutiliza cache de métricas;
- Evolução Operacional é endpoint separado/lazy e cacheado;
- oportunidades do dia têm memoização curta de 60s no namespace operacional.

Ranking padrão (`/motoristas/` sem filtros especiais) reutiliza a mesma fotografia oficial cacheada usada pelo Dashboard.

Logs `PERF` medem Dashboard, Operação, Entregas, Motoristas, Retidos e WhatsApp.

Não há benchmark HTTP válido desta entrega porque Django/banco não estavam disponíveis no ambiente de empacotamento.

## 14. Mapa

Regra absoluta: **MUNICÍPIO != BAIRRO**.

`geodata_loader.py`:

- aceita apenas Polygon/MultiPolygon;
- rejeita tipos city/town/municipality/administrative/county/state;
- valida município retornado;
- exige que nome/endereço retornado corresponda ao bairro normalizado;
- recusa Zona Rural, nome do próprio município e padrões de estabelecimento/logradouro;
- erros de fetch tentam novamente após 1h;
- “não encontrado” tenta novamente após 7 dias;
- retry manual é suportado.

Aliases centralizados em `apps/operations/geo.py`, incluindo ALMIR GRABRIEL→ALMIR GABRIEL e PARK VERDE→PARQUE VERDE.

O limite artificial de 25 bairros foi removido. Falta de geometria não apaga os dados operacionais: lista/ranking/fallback continuam.

Cache de resumo geográfico usa namespace operacional versionado.

## 15. Migrations / banco

A baseline antiga usava criação/sincronização menos formal. v0.9.1.0 traz migrations iniciais para apps existentes e migrations específicas para:

- Ranking V3;
- `DriverPortalAccessRequest`;
- `ProofRetention`;
- `ProofPickupAttempt`.

Scripts não executam `makemigrations` criativo. Apenas `makemigrations --check --dry-run`.

Entry point Docker usa `migrate --fake-initial --noinput` para permitir adoção das tabelas pré-existentes.

**Antes da produção:** backup do banco real, clone/cópia de homologação, `check`, `makemigrations --check`, `migrate --plan`, migrate e conferência dos dados. Isso ficou externamente pendente porque Django não estava instalado no ambiente de empacotamento.

## 16. VPS

Docker Compose esperado:

- nginx;
- web;
- postgres;
- redis;
- worker;
- beat;
- robot-worker;
- whatsapp.

`restart: unless-stopped`. Sem domínio inicialmente: `http://IP_PUBLICO_DA_VPS`.

Comandos:

```bash
git pull
docker compose up -d --build
docker compose ps
docker compose logs --tail=200 web
docker compose logs --tail=200 robot-worker
docker compose logs --tail=200 whatsapp
```

## 17. Windows

```bat
EXECUTAR_LOCAL.bat
EXECUTAR_ONLINE.bat
PARAR_LOCAL.bat
PARAR_ONLINE.bat
INSTALAR_BOT_WHATSAPP.bat
VERIFICAR_BUILD.bat
```

Logs principais em `local_data/logs/` e logs específicos SSW/WhatsApp.

## 18. Git / dados que nunca entram

- `.env`, `.env.local`, `.env.vps`;
- senha/token/chaves;
- credenciais SSW;
- sessão Baileys;
- bancos/dumps;
- logs reais;
- `local_data`;
- media/uploads reais;
- relatórios SSW reais;
- `node_modules`;
- `.venv`.

## 19. QA realmente executado nesta entrega

Passaram no ambiente de empacotamento:

- `python -m compileall`;
- `node --check static/js/app.js`;
- `node --check whatsapp_bridge/server.mjs`;
- todos os scripts portáteis/estáticos em `scripts/qa/`;
- fórmula V2/V3;
- migrations estáticas/boot sem criação automática;
- rotas/templates estáticos;
- Baileys/telefone BR estático;
- VPS/Docker Compose estático;
- mock do contrato robot SSW opção 036;
- manifesto 6/6 do core homologado;
- comparação integral 17/17 de `robot_ssw` contra a árvore de origem;
- patch dry-run e comparação final durante empacotamento.

## 20. HOMOLOGAÇÃO EXTERNA PENDENTE

- `python manage.py check`;
- `python manage.py makemigrations --check` real com Django;
- `migrate` SQLite de teste;
- upgrade em cópia de PostgreSQL real;
- suíte Django completa;
- benchmark de telas com cache frio/quente;
- regressão com os 10 relatórios SSW reais privados (não estavam no pacote desta sessão);
- SSW opção 036 real com credenciais/rede;
- WhatsApp/Baileys real com aparelho;
- UI visual 1920x1080, 1366x768, 1280x720, 1024, tablet e mobile;
- reboot real da VPS/containers;
- comparação/rebase com eventual baseline funcional oficial v0.9.0.0 não fornecida.

## 21. Como criar a próxima versão

1. obter a baseline completa v0.9.1.0 desta entrega;
2. copiar para uma árvore de trabalho;
3. nunca editar o ZIP/baseline original;
4. alterar fora de `robot_ssw` sempre que possível;
5. executar QA;
6. validar migrations e banco em ambiente Django;
7. comparar `robot_ssw` byte a byte;
8. atualizar VERSION/CHANGELOG/docs;
9. gerar patch por diff;
10. aplicar patch em cópia limpa da baseline;
11. comparar árvore resultante com a nova baseline;
12. remover secrets/runtime;
13. gerar ZIPs + SHA-256;
14. documentar claramente toda homologação ainda pendente.

## 16. Empacotamento da v0.9.1.0

O PATCH foi calculado contra a origem efetivamente fornecida e passou em dry-run sobre uma cópia limpa: após aplicação, caminhos e SHA-256 ficaram idênticos à baseline canônica v0.9.1.0. O payload não contém arquivos de `robot_ssw/`.

A ressalva de linhagem permanece: caso apareça uma baseline funcional oficial v0.9.0.0 diferente da árvore recebida, não force o patch; faça rebase/diff e repita QA, migrations, robot integrity e patch dry-run.

## Correção de migrations da build final v0.9.1.0

Durante execução real do `EXECUTAR_ONLINE.bat` no Windows, `makemigrations --check` propôs apenas renomes de índices. A build final corrigida fixa explicitamente nos models os mesmos nomes já existentes nas migrations versionadas. **Não criar as migrations `RenameIndex` sugeridas pela build anterior.** Com a build corrigida, reexecutar `makemigrations --check`; o esperado é `No changes detected`.
