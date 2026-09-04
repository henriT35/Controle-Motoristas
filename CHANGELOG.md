# Changelog

## 0.9.2.0 — Avaliação V3 explicável, ROM13 manual e retenção pelo estado atual — 2026-09-03

### Estabilização de performance R3 — período padrão aquecido + gráfico + diagnóstico por sessão
- warmup passa a respeitar o `period_default` real (mês, 7d/30d/60d/90d, semana, ano etc.), evitando que o Dashboard abra em uma janela diferente daquela previamente aquecida;
- payload da Evolução Operacional é pré-calculado no startup/pós-import, mantendo o gráfico lazy-loaded sem devolver ~2 s de processamento ao primeiro clique;
- Entregas Gerais elimina N+1 do comprovante com `select_related("cte__retained_proof")` e reaproveita o conjunto de CT-es entregues já calculado, reduzindo queries redundantes;
- executores Windows gravam `PERF session.start` depois do warmup, separando navegação real de preparação do sistema;
- `PERFORMANCE_DIAGNOSTICO.bat` passa a mostrar por padrão somente a sessão atual, com última/média/máxima por tela, sem misturar medições antigas de 10–20 s;
- `robot_ssw/` permanece byte a byte idêntico à R2.

### Estabilização de performance R2 — snapshots persistentes + histórico de Retirada Exata
- diagnóstico real no Windows confirmou Dashboard frio de até 17,15 s com SQL de apenas 0,42 s; o gargalo era o cálculo Python do Ranking (`ranking.movements` + `ranking.events`), enquanto o Dashboard quente já respondia em ~0,12 s;
- `DriverScoreSnapshot` passa a armazenar a fotografia completa necessária ao Dashboard/Ranking, não apenas o breakdown explicativo;
- em cache miss, `calculate_driver_metrics()` tenta a fotografia persistente antes de reconstruir movimentos, eliminando o custo de 10–17 s do usuário quando o cache global é invalidado;
- snapshot é recalculado em startup/pós-import/validações e protegido por lock compartilhado para impedir cache stampede/reconstruções concorrentes;
- `ImportRun` deixa de invalidar o cache global a cada simples mudança de estado; a importação já invalida explicitamente quando os fatos operacionais foram persistidos;
- Qualidade agrega contagens ROM13 no banco por motorista/status antes de calcular a nota;
- Regularidade de Retirada Exata passa a ser agrupada por **motorista + cliente/parada + data operacional**: vários comprovantes na mesma visita geram no máximo uma obrigação de Regularidade;
- recuperação informada como `RETIREI` só cumpre definitivamente a Regularidade após aprovação; evidência pendente não penaliza e evidência rejeitada não permanece como cumprimento;
- Retiradas Exatas são materializadas automaticamente pela rota desde 01/09/2026, inclusive se o motorista nunca abrir o Portal;
- o backfill histórico usa somente provas que estavam determinísticamente ativas no dia e considera `CTe.delivered_at` para não criar falsa obrigação quando a baixa SSW foi reconciliada depois;
- Central de Avaliações e KPI do Dashboard passam a contar omissões por parada/dia, não por número de comprovantes.

### Hotfix de compatibilidade de índice — execução real Windows
- corrige `models.E034` detectado pelo `manage.py makemigrations --check`/system check no Windows: o índice `proofs_opp_driver_date_kind_idx` possuía 31 caracteres e excedia o limite portável de 30 caracteres validado pelo Django;
- renomeia o índice versionado para `proofs_opp_drv_date_kind_idx` (28 caracteres) tanto no model quanto na migration v0.9.2.0;
- atualiza os contratos de QA para impedir regressão com nomes de índices acima de 30 caracteres;
- não altera dados, regras de avaliação, `robot_ssw/` ou semântica do índice.

### Avaliação dos motoristas
- Nota Geral V3 permanece única em 0–100, com pesos padrão configuráveis: Gestão de Comprovantes 50%, Qualidade Operacional 35% e Regularidade 15%.
- produtividade bruta (CT-es, entregas, peso, frete, volume, romaneios) continua apenas como estatística operacional e não aumenta a nota.
- Qualidade Operacional passa a usar somente ROM13 validado manualmente pelo coordenador como responsabilidade do motorista; evento pendente/VERIFICAR/sem responsabilidade é neutro.
- cada nova tentativa com novo ROM13 pode gerar nova avaliação; repetição do mesmo ROM13 na mesma tentativa é idempotente.
- Regularidade deixa de ser 100 fixo e mede ações obrigatórias efetivamente apresentadas/cumpridas. Ouro ignorado é neutro.
- Retirada Exata sem manifestação após o encerramento vira omissão de Regularidade; “Ainda não liberado” exige observação e “Não foi possível tentar” exige justificativa.
- recuperação só pontua após validação e sempre para `recovery_driver`; `original_driver` permanece imutável como origem.

### Portal e coordenação
- Portal passa a explicar Nota Geral, três pilares, contribuição por peso, ROM13 negativos/neutros/pendentes, Regularidade, bônus e histórico de snapshots.
- projeção de uma oportunidade usa a mesma fórmula V3, incluindo teto de bônus e efeito da Retirada Exata em Gestão/Regularidade.
- nova Central de Avaliações permite ao coordenador classificar ROM13 como responsabilidade, sem responsabilidade ou VERIFICAR, com motivo visível obrigatório quando houver responsabilização e observação interna separada.
- decisões podem ser reabertas/revertidas com auditoria e invalidação de cache.

### Retenções / SSW
- ROM34 passa a ser tratado definitivamente como origem histórica da retenção, não como penalização de Qualidade.
- estado consolidado atual do CTRC governa a ação: 34 = retenção ativa; 1/ENTREGUE = resolvido automaticamente pelo SSW; outros estados = ACOMPANHANDO_SSW.
- baixa automática por ENTREGUE não inventa `recovery_driver`, não concede bônus e registra `resolution_source=SSW`.
- datas/horários técnicos inferidos não podem vetar uma baixa atual por ENTREGUE.
- snapshots de relatórios importados fora de ordem não podem regredir o estado atual já observado em tentativa mais nova.
- comando `reconcile_retained_proofs --dry-run` permite revisar a base existente antes de aplicar a reconciliação.
- regressões reais BNU046259-4 e CWB055520-7 cobertas por QA de parser sobre 12 relatórios SSW reais (27.126 linhas).

### Auditoria, cache e automação
- eventos de qualidade, oportunidades apresentadas, omissões, ressalvas, validações, reaberturas e reconciliações deixam trilha auditável.
- cache operacional é invalidado nas mudanças que afetam nota/retenção.
- housekeeping diário fecha EXACT sem resposta, expira GOLD de forma neutra, sincroniza ROM13/ressalvas e persiste snapshots de nota.
- `robot_ssw/` permanece congelado e fora das alterações funcionais.

### QA / release
- QA Python/estático, contrato do robô, JS, rotas/templates, Baileys, VPS e regressões reais executados no ambiente disponível.
- Django runtime não está instalado no ambiente de empacotamento; `manage.py check`, `makemigrations --check`, migrations reais, suíte Django e homologações SSW/WhatsApp/VPS permanecem explicitamente como HOMOLOGAÇÃO EXTERNA PENDENTE.

## 0.9.1.0 — Estabilização, homologação, performance e acabamento — 2026-09-03

### Hotfix runtime do Dashboard / cache operacional
- corrige `HTTP 500` confirmado em execução real no Windows ao abrir `/dashboard/`;
- causa raiz: `apps/core/services.py` passou a usar `cache` e `versioned_key()` durante a otimização v0.9.1.0, mas os dois imports não haviam sido incluídos no módulo;
- adiciona `from django.core.cache import cache` e `from .cache import versioned_key`;
- nenhum model, migration, regra temporal ou arquivo de `robot_ssw/` foi alterado;
- regressão estática do contrato v0.9.1.0 agora exige explicitamente esses imports para impedir retorno do `NameError`.

### Integridade e regras operacionais
- preserva ROM85 como evidência preferencial de saída, ROM34 como origem preferencial da retenção e CTRC34 apenas como fallback;
- mantém código 13 encerrando a tentativa e impede promoção de romaneios históricos por CTRC consolidado;
- amplia regressão permanente dos pós-retenção ambíguos para 60, 53 e 91, todos em `VERIFICAR` até evidência conclusiva;
- mantém `original_driver` e `recovery_driver` separados e dá crédito de recuperação somente ao motorista que realmente recuperou após validação.

### Ranking V3 e Portal
- consolida uma única Nota Geral 0–100 com pesos padrão 50/35/15 configuráveis;
- produtividade bruta permanece fora da nota e somente como estatística operacional;
- normaliza uma causa principal de impacto por tentativa para evitar punição duplicada;
- adiciona bônus configuráveis para recuperação exata e ouro, com teto;
- Portal mostra posição, nota, distância para a posição superior e projeção de nota/posição;
- adiciona solicitação de novo link, obrigatoriamente revisada por coordenador antes de regenerar acesso;
- adiciona `ProofRetention` e `ProofPickupAttempt` para ressalva, retirada exata e Oportunidade de Ouro;
- “Ainda não liberado” e oportunidade ouro ignorada não geram penalização automática.

### Performance
- adiciona instrumentação `PERF` por tela/componente;
- adiciona cache operacional versionado, Redis em PostgreSQL/VPS e LocMem como fallback local;
- invalidação centralizada após fatos operacionais e configuração do ranking;
- série pesada da Evolução Operacional pode ser carregada separadamente;
- memoização temporária das oportunidades exatas do dia;
- Central WhatsApp evita carregar todo histórico de mensagens e busca apenas a mensagem mais recente por motorista.

### SSW / UX
- “Atualizar agora” usa AJAX/fetch e acompanha o job sem redirecionar o usuário;
- Central de Rotinas mantém período recente/fixo, janela, frequência, próxima execução, heartbeat e ações;
- modal/UX recebeu regras responsivas para telas menores;
- migrations passam a ser formais; scripts deixam de criar migrations automaticamente.

### WhatsApp / segurança
- mantém Node.js + Baileys, sessão persistente e variações brasileiras com/sem o nono dígito;
- Central WhatsApp mantém lista única por motorista;
- QR permanece em card compacto único;
- redirecionamentos baseados em `next` agora validam host para evitar open redirect;
- solicitação pública de novo acesso recebe throttle leve e resposta genérica contra enumeração;
- links enviados respeitam `PANEL_PUBLIC_BASE_URL`.

### Mapa
- reforça a regra absoluta MUNICÍPIO != BAIRRO;
- rejeita geometria municipal/administrativa como bairro;
- centraliza aliases como `ALMIR GRABRIEL → ALMIR GABRIEL` e `PARK VERDE → PARQUE VERDE`;
- cache de erro expira e suporta retry;
- remove o limite artificial de 25 bairros no pedido de geometria;
- sem geometria confiável, mantém o dado operacional sem inventar polígono.

### Correção de estabilização das migrations
- corrige divergência observada no Windows em `makemigrations --check`, que sugeria apenas `RenameIndex` para índices já existentes;
- a causa era o uso de nomes automáticos de `models.Index` nos models enquanto as migrations já tinham nomes versionados explícitos;
- os models agora declaram exatamente os mesmos nomes dos índices existentes nas migrations, evitando gerar migrations cosméticas e preservando o banco atual;
- não foi criada migration de rename e nenhum índice físico precisa ser renomeado por esta correção;
- adicionada regressão estática específica para impedir o retorno desse drift.

### QA e linhagem
- `python compileall`, sintaxe Node/JS, QA portátil, fórmula V3, contratos estáticos, Baileys, telefone BR, VPS estático e mock do robô passaram no ambiente disponível;
- core manifest do `robot_ssw` passou e a comparação integral com a árvore de origem é executada no empacotamento;
- Django/Docker não estavam instalados no ambiente de empacotamento; runtime/migrations reais, benchmark HTTP, WhatsApp real, SSW real, UI multi-resolução e regressão com os 10 relatórios privados permanecem como homologação externa;
- a árvore fornecida não contém baseline funcional oficial v0.9.0.0; o PATCH registra explicitamente a árvore de continuidade efetivamente usada como origem.
- patch dry-run sobre cópia limpa da origem efetivamente fornecida produz árvore canônica idêntica à baseline v0.9.1.0 (0 diferenças de caminho/conteúdo); `robot_ssw` não entra no payload.

---

## 0.8.2.0 — UX responsiva, gráfico ampliável e rotinas SSW

### Responsividade / navegação
- Sidebar passa a reservar espaço fixo para a conta do usuário e torna a navegação interna rolável em telas de pouca altura, evitando que Configurações/Admin sejam encobertos.
- Modo compacto reduz alturas e espaçamentos em monitores menores; a conta ganha identificação por tooltip quando a sidebar está recolhida por largura.
- Conteúdo, painéis, KPIs e cabeçalhos recebem proteção extra contra overflow horizontal.

### Dashboard / Evolução Operacional
- Gráfico anual recebe `dataZoom` por roda do mouse/gesto e slider inferior.
- Novo botão **Ampliar** abre o gráfico quase em tela cheia e `Esc` fecha.
- Novo botão **Todo período** restaura o zoom 0–100%.
- Séries densas deixam de desenhar todos os pontos ao mesmo tempo, preservando leitura e desempenho em períodos longos.

### Automação SSW / causa raiz
- A v0.8.1.0 tinha Celery Beat configurado para a VPS, mas `EXECUTAR_LOCAL.bat`/`EXECUTAR_ONLINE.bat` iniciavam somente o web server no Windows. Portanto o scheduler automático nunca ficava vivo no modo em que a homologação estava sendo feita.
- Novo comando `run_ssw_scheduler` mantém a agenda ativa no Windows e é iniciado/parado junto com os scripts local/online.
- `local_data/ssw_scheduler_state.json` registra heartbeat/último ciclo para a tela mostrar se o scheduler está realmente online.

### Rotinas configuráveis
- A configuração deixa de ser um único intervalo global e passa a aceitar múltiplas rotinas.
- Cada rotina possui nome, tipo de período (`RECENT` ou `FIXED`), intervalo de 15–1440 min, janela diária e estado ativo/pausado.
- `RECENT` é indicada para acompanhar as rotas do dia (ex.: últimos 2 dias a cada 2 horas).
- `FIXED` permite manter um período maior sendo reconsultado; intervalos longos são quebrados em janelas mensais pela fila já existente.
- Ciclo anterior ainda QUEUED/DISPATCHED/RUNNING bloqueia novo disparo da mesma rotina; o dispatcher global continua executando somente um robô por vez.
- Botão **Executar agora** por rotina e botão rápido anterior permanecem disponíveis.
- Configuração antiga `{enabled, interval_minutes}` é convertida automaticamente para uma rotina recente, sem migration.

### Compatibilidade
- Base do patch: **v0.8.1.0**.
- Nenhuma migration/model novo nesta rodada.
- Core `robot_ssw` permanece congelado e deve ser byte a byte idêntico à v0.8.1.0.
- VPS continua usando Celery Beat; Windows usa o management command persistente com a mesma função `run_due_routines()`.

## 0.8.1.0 — Correção temporal de rotas e retenções

### Retenção / comprovantes
- ROM `34 - MERCADORIA EM CONFERENCIA NO CLIENTE` passa a ser a evidência principal da tentativa que originou a retenção.
- CTRC=34 continua válido como fallback de estado consolidado, mas não pode mais roubar o romaneio/motorista quando existir ROM34.
- Bases antigas são reparáveis pelo novo comando `reconcile_operational_logic` / `RECONCILIAR_LOGICA_v0_8_1_0.bat`.
- Novo status `VERIFICAR`: usado quando houve retenção e o CTRC mais recente mudou para um código não conclusivo (ex.: 60 DOCUMENTOS, 53 AVARIA, 91 INDENIZAÇÃO), sem prova de entrega nem de retenção ainda ativa.
- Recuperação automática continua restrita a ocorrência de entrega comprovada; baixa manual validada continua soberana.

### Reentrega / código 13
- `13 - ENTREGA PREJUDICADA PELO HORARIO` agora fecha explicitamente aquela tentativa para o snapshot de rota atual.
- `CTRC=85` não promove mais todos os romaneios históricos do CT-e. O resolver ao vivo escolhe no máximo uma tentativa elegível por CT-e.
- O romaneio/motorista antigo permanece no histórico e no ranking da tentativa em que recebeu o 13; a nova tentativa pode pertencer a outro romaneio e outro motorista sem duplicar a rota diária.

### Reconstrução histórica segura
- Relatórios 036 antigos com `DATA OCORR ROM` vazia podem recuperar data operacional quando existe o MESMO fato ROM e CTRC datado de forma unívoca.
- CTRC apenas completa a data de um fato ROM já existente; não cria tentativa.
- Se o mesmo fato aparece em mais de uma tentativa, há múltiplas datas CTRC, ou o romaneio recebe dias conflitantes, nenhuma data é inventada.
- Emissão, previsão e instante de importação continuam proibidos como fonte automática para reescrever o histórico operacional.
- Dashboard, Operação e métricas de motorista passam a consumir a mesma reconstrução temporal.

### QA com o lote real enviado em 02/09/2026
- 10 relatórios / 25.145 linhas analisadas.
- 1.378 CT-es com histórico de retenção; 15 casos reproduziram mudança de origem ao priorizar ROM34 sobre CTRC34.
- 12 retenções terminaram em estado CTRC não conclusivo e entram na regra `VERIFICAR`.
- 5 CT-es reproduziram o cenário de ROM13 antigo + nova tentativa/motorista com CTRC85, usado como regressão da duplicidade diária.
- Reconstrução histórica encontrou mais de 1,2 mil romaneios com âncora segura; conflitos permanecem sem data automática.

### Compatibilidade
- Base do patch: **v0.8.0.1**.
- Core `robot_ssw` permanece congelado e byte a byte idêntico à v0.8.0.1.
- O novo status é uma escolha do campo existente; não adiciona coluna/tabela. O bootstrap local pode gerar a alteração de choices conforme o mecanismo já existente do projeto.

## 0.8.0.1 — Hotfix inicialização SSW / require_POST

### Causa raiz
- A v0.8.0.0 adicionou os endpoints POST de configuração da automação SSW e de atualização imediata usando `@require_POST`, mas `apps/ssw/views.py` não importava `require_POST`.
- O Django carregava `config/urls.py` durante `makemigrations`/`check` e interrompia o boot com `NameError: name 'require_POST' is not defined`.

### Correção
- Adicionado `from django.views.decorators.http import require_POST` em `apps/ssw/views.py`.
- Adicionada checagem estática de decorators para impedir regressão equivalente no módulo SSW.
- Nenhuma alteração de models/migrations, banco, WhatsApp, automação ou core do `robot_ssw`.

### Compatibilidade
- Base obrigatória do patch: **v0.8.0.0**.
- `robot_ssw` permanece congelado e byte a byte idêntico à v0.8.0.0.

## 0.8.0.0 — VPS Hostinger, automação SSW e WhatsApp em lote

### VPS / GitHub
- Nova arquitetura oficial Docker Compose para deploy por `git clone`/`git pull` em VPS Hostinger Ubuntu.
- Serviços isolados: Nginx, Django/Gunicorn, PostgreSQL, Redis, Celery Worker, Celery Beat, worker SSW Playwright e Node/Baileys.
- Acesso inicial sem domínio por `http://IP_PUBLICO_DA_VPS`.
- Todos os serviços usam `restart: unless-stopped`; o Docker é habilitado no boot pelo instalador VPS quando possível.
- Volumes persistentes preservam PostgreSQL, Redis, uploads, importações, `local_data` e sessão Baileys entre rebuilds.
- Rotas `/whatsapp/internal/` são bloqueadas pelo Nginx; o bridge usa rede Docker interna + token compartilhado.

### Robô SSW na própria VPS
- O core `robot_ssw` permanece byte a byte idêntico à v0.7.1.1.
- A adaptação Linux ocorre somente no `Dockerfile.robot`, variáveis e entrypoint: Playwright/Chromium headless, inbox Linux e credenciais injetadas em runtime.
- `run_robot_import` é roteado para a fila Celery `ssw`, consumida por um worker exclusivo com concorrência 1.
- Django/WhatsApp continuam disponíveis se o navegador SSW travar ou for reiniciado.

### Automação SSW
- Celery Beat acorda a cada minuto e consulta a configuração persistente em `local_data/ssw_schedule.json`.
- A frequência real pode ser alterada no Painel entre 15 e 1440 minutos sem reiniciar containers.
- Padrão inicial: 60 minutos.
- Novo botão **Atualizar agora** cria uma FAST imediatamente usando a mesma deduplicação/lock da fila existente.
- Automação pode ser ativada/desativada pela tela SSW; a reconciliação mensal acompanha o estado da automação.

### WhatsApp / motoristas
- Novo botão **Gerar e enviar para todos** cria mensagens para todos os motoristas ativos/habilitados; quem tem operação recebe resumo do dia e quem não tem recebe o link geral do Portal.
- O Baileys envia a fila sequencialmente, com atraso configurável entre mensagens.
- Números brasileiros são verificados automaticamente nas duas formas com/sem o 9 após o DDD usando `onWhatsApp`; o número efetivamente resolvido é registrado na tentativa de envio.
- Nova seção **Cadastros WhatsApp** permite editar número e habilitação de qualquer motorista diretamente na Central.

### Banco / segurança / operação
- PostgreSQL em Docker usa campos de conexão separados, evitando quebra por caracteres especiais na senha dentro de URL.
- Healthcheck `/healthz/` valida aplicação + banco para Docker/Nginx.
- Cookies seguros passam a ser configuráveis por ambiente; o perfil VPS sem domínio usa HTTP/IP e `DJANGO_SECURE_COOKIES=0`. HTTPS continua recomendado para etapa posterior.
- Sem alteração de models e sem migration nova.

### Compatibilidade
- Base do patch: **v0.7.1.1**.
- `robot_ssw`: 17/17 arquivos idênticos à v0.7.1.1.
- Modo Windows/local continua disponível.

## 0.7.1.1 — Hotfix instalador Baileys / Node portátil

### Causa raiz
- O instalador da v0.7.1.0 conseguia executar `node.exe` e `npm.cmd` pelo caminho absoluto do Node portátil, porém não adicionava `tools\node` ao `PATH` do processo.
- Durante `npm install`, o pacote Baileys executa um script lifecycle que chama `node` pelo shell. Esse subprocesso não encontrava `node` e abortava com `'node' não é reconhecido como um comando interno ou externo`.
- A instalação interrompida podia deixar `whatsapp_bridge\node_modules` parcialmente criado, gerando avisos `EPERM` nas tentativas seguintes.

### Correção
- O diretório do Node selecionado é adicionado ao `PATH` antes de qualquer `npm install`, sendo herdado pelos subprocessos/lifecycle scripts.
- O instalador também define `NODE` e `npm_node_execpath` para apontar explicitamente ao executável selecionado.
- Antes de instalar, é executada uma prova real `node.exe -v` resolvida pelo `PATH`; a instalação é bloqueada com mensagem clara se essa prova falhar.
- Instalações parciais de `node_modules` são removidas com tentativas e fallback `rmdir`; somente o processo Node pertencente ao `whatsapp_bridge/server.mjs` deste projeto pode ser encerrado durante a limpeza.
- Se Baileys/Pino/QRCode já estiverem completos, o instalador apenas valida a instalação em vez de reinstalar.

### Compatibilidade
- Base obrigatória do patch: **v0.7.1.0**.
- Sem alteração de models/migrations.
- Nenhuma alteração no protocolo QR/bridge Baileys.
- `robot_ssw` permanece congelado.

## 0.7.1.0 — WhatsApp Baileys / Node.js

### Decisão arquitetural
- O login anterior por Chrome/Edge/Playwright/CDP foi aposentado depois de múltiplas falhas de bootstrap/QR em homologação Windows.
- O WhatsApp passa a usar **Baileys 6.7.24 em Node.js 20+**, sem navegador no pareamento ou no envio.
- O QR é recebido diretamente em `connection.update.qr` e convertido em `local_data/whatsapp/qr.png`.
- A sessão multi-dispositivo fica em `local_data/whatsapp/baileys_auth/`.

### Integração Django ↔ Node
- A fila `WhatsAppMessage` continua sendo a fonte de verdade do Painel.
- O bridge Node consome a fila por duas rotas internas (`claim` e `result`) protegidas por loopback + token aleatório local.
- Mensagens `SENDING` abandonadas por mais de 3 minutos viram `FAILED` para evitar envio duplicado; o reenvio fica explícito para o coordenador.
- O bridge não registra listener `messages.upsert`; não foi implementada leitura/resposta automática de conversas.

### Remoções
- Removido `apps/messaging/cdp_session.py`.
- Removido `apps/messaging/management/commands/whatsapp_bot.py`.
- Preview de navegador e diagnóstico `post_logout` deixam de existir na UI atual.
- `websocket-client` deixa de ser dependência do módulo WhatsApp. Playwright permanece por causa do robô SSW.

### Instalação
- `INSTALAR_BOT_WHATSAPP.bat` agora prepara Node.js + Baileys.
- Se Node.js 20+ não existir, o instalador baixa Node.js 24.20.0 LTS portátil para `tools/node`.
- Dependências Node ficam em `whatsapp_bridge/node_modules/` e não são distribuídas dentro da baseline.

### Compatibilidade
- Base do patch: **v0.7.0.1**.
- Sem alteração de models e sem migration nova.
- Fluxo SSW e `robot_ssw` não fazem parte desta alteração.

## 0.7.0.1 — Hotfix QR direto e confirmação ao vivo da rota

### WhatsApp — causa raiz do erro da v0.7.0.0
- O navegador real (Edge/Chrome) iniciava e disponibilizava a porta CDP normalmente.
- O Playwright chegava a abrir o websocket de DevTools, porém `BrowserType.connect_over_cdp()` ficava aguardando a construção do `BrowserContext` até estourar `Timeout 15000ms`, bloqueando o fluxo antes de o Painel conseguir capturar o QR.
- O pareamento não precisa dessa camada de abstração. O navegador já expõe tudo que o Painel precisa pelo protocolo DevTools.

### WhatsApp — correção
- Novo adaptador `apps/messaging/cdp_session.py` usa CDP diretamente por `websocket-client`.
- Chrome/Edge é iniciado em `about:blank` com profile exclusivo e porta de depuração apenas em `127.0.0.1`; depois a aplicação navega para `web.whatsapp.com` via `Page.navigate`.
- Captura do QR, screenshot de diagnóstico, leitura de estado, recarga, foco e Enter de envio passam a usar CDP diretamente.
- `post_logout=1` deixa de ser tratado como falha imediata: o bot aguarda até 20s como estado transitório, faz uma única navegação limpa para `/` e só troca de navegador se o estado persistir por 45s sem QR.
- `Playwright.connect_over_cdp()` foi removido do caminho do Bot WhatsApp; Playwright continua no projeto para o robô SSW e apenas pode fornecer o caminho do Chromium como fallback.
- Estado do bot passa a registrar `browser_mode=RAW_CDP`.
- Nova dependência local: `websocket-client>=1.8`, instalada automaticamente pelo bootstrap/`INSTALAR_BOT_WHATSAPP.bat`.

### Operação de Hoje — rota com 85 atual ainda em Planejamento
- A temporalidade canônica v0.7.0.0 permanece correta para histórico, porém era rígida demais para a fotografia ao vivo: um CT-e cujo estado consolidado atual fosse `SAIDA PARA ENTREGA` podia continuar na seção Planejamento quando a trilha ROMANEIO não tinha data utilizável.
- Criada confirmação **ao vivo** apenas para a data corrente: romaneios com CT-e atualmente em `SAIDA PARA ENTREGA` entram na Operação de Hoje e saem do Planejamento.
- Esse fallback nunca é usado para datas históricas, nunca cria ocorrência retroativa e nunca altera a data canônica armazenada/inferida do romaneio.
- Dashboard/Entregas em períodos que incluem hoje também recebem essa fotografia ao vivo para manter a reconciliação do dia corrente.

### Compatibilidade
- Base obrigatória do patch: **v0.7.0.0**.
- Sem alteração de models e sem migration nova.
- `robot_ssw` permanece congelado e deve ser byte a byte idêntico à v0.7.0.0.

## 0.7.0.0 — Temporalidade canônica, Entregas Gerais e navegação operacional

### Causa raiz — romaneios antigos em datas recentes
- A regra anterior incluía um romaneio em qualquer dia que tivesse **qualquer ocorrência ROMANEIO datada** no período. Assim, uma entrega/retenção posterior podia fazer o mesmo romaneio reaparecer em uma data nova.
- O carry-over destinado ao dia corrente também era aplicado em consultas históricas, permitindo que rotas antigas contaminassem fotografias já encerradas.
- O importador antigo identificava ocorrência ROM sem incluir a tentativa/movimento, enquanto CTRC consolidado ainda podia permanecer vinculado a movimento. Isso confundia fato da tentativa com estado do documento.

### Correção temporal
- Criada uma fonte canônica única por romaneio: **primeira ocorrência 85 datada = CONFIRMED; sem 85, primeiro fato SSW_ROMANEIO datado = INFERRED; sem fato = PLANNED / data não confirmada**.
- Cada romaneio passa a possuir no máximo uma data operacional canônica; eventos ROM posteriores não migram a rota.
- Emissão, `movement_date`, importação, CTRC consolidado e evento de outra tentativa deixam de materializar silenciosamente uma data operacional.
- Carry-over passa a existir exclusivamente no dia corrente.
- Fotografia histórica de entrega deixa de usar `movement_date` quando a ocorrência ENTREGUE não possui data de negócio.
- ROM34 sem data usa a data canônica da rota quando disponível; sem essa evidência, a origem histórica permanece não confirmada.

### Dashboard e Operação do Dia
- Dashboard, Operação do Dia e Entregas Gerais passam a consumir a mesma fonte temporal de domínio.
- A série diária de entregas é reconciliada pela data operacional da tentativa/romaneio; um ENTREGUE posterior não move a rota para outro ponto do gráfico.
- Novo KPI **Retidos no dia**, com quantidade originada naquele dia, recuperados posteriormente e ainda abertos.

### Entregas Gerais e detalhe do CT-e
- Nova tela **Entregas Gerais** com período, busca, motorista, cliente, romaneio, cidade, bairro, ocorrência, entrega, tentativa, retenção, comprovante, ordenação e paginação.
- CT-e na rota passa a ser clicável. Nova ficha detalha documento, NF, valores, peso, volumes, cliente, tentativas, datas operacionais, ocorrências ROM/CTRC e comprovante/evidências.
- Ordenação por data usa data operacional, não emissão do romaneio.

### Navegação
- O menu lateral memoriza por sessão a última URL de cada módulo, incluindo filtros, período, busca, ordenação e página.
- Fluxos Rota → CT-e → Voltar preservam o contexto anterior por URL segura.

### Mapa
- Falha ou ausência de polígonos não bloqueia mais a consulta: ranking, KPIs e lista textual de regiões/bairros permanecem utilizáveis.
- Drill-down por bairro não contabiliza registros de outros municípios como “sem localização suficiente”.
- O indicador de registros sem localização suficiente ganhou diagnóstico por motivo e amostra de registros.

### Importação SSW
- Identidade de ocorrência **ROMANEIO** passa a incluir o movimento/tentativa.
- Ocorrência **CTRC** permanece consolidada no CT-e e sem vínculo de movimento.
- Reparação de vínculo legado só ocorre quando o evento estava sem movimento; um evento já ligado a outra tentativa nunca é migrado silenciosamente.

### Portal do Motorista — câmera mobile
- Corrigido o seletor que misturava `capture=environment` com `application/pdf` no mesmo input e fazia alguns celulares ignorarem a câmera.
- O Portal agora separa **Tirar foto** (`image/*` + câmera traseira) de **Escolher arquivo** (galeria/imagem/PDF).
- Backend aceita as duas origens e mantém compatibilidade com o campo antigo `evidence`.
- O envio continua criando submissão pendente; não existe baixa automática do comprovante.

### WhatsApp — núcleo de pareamento refeito
- O diagnóstico real da v0.6.0.6 mostrou que `Browser.setPermission` retornava sucesso, porém o navegador continuava reportando `persistentStoragePermission=prompt` e `storagePersisted=false`; esse override deixou de ser usado como solução principal.
- O navegador de pareamento agora é iniciado como **processo normal do Chrome/Edge**, fora do launcher do Playwright e sem `--enable-automation`.
- O Playwright se conecta somente depois via CDP local (`127.0.0.1`) para capturar o QR e manter o envio, reduzindo interferência no bootstrap do WhatsApp Web.
- Nova tela dedicada **Conectar WhatsApp**: a função principal é gerar, exibir e atualizar o QR Code diretamente no Painel.
- A procura/captura do QR passou a ocorrer **antes** de classificar `post_logout` ou erro de banco/storage. Se o QR está visível, ele é mostrado mesmo que a URL esteja transitando por um estado de logout.
- Cada novo pareamento continua usando profile exclusivo; sessão só é promovida depois de conexão real.
- A porta de depuração fica restrita ao loopback e o navegador continua sendo encerrado junto com o bot.

### Compatibilidade
- Base obrigatória do patch: **v0.6.0.6**.
- Sem alteração de models e sem migration nova.
- Portal mantém token individual e validação de comprovantes.
- `robot_ssw` permanece congelado e deve ser validado por hash antes da publicação.

## 0.6.0.6 — WhatsApp Web: durableStorage / erro de banco antes do QR

### Causa raiz confirmada pelo diagnóstico real
- A execução iniciou em `NEW_PAIRING` com profile inédito, portanto não estava reutilizando a sessão antiga.
- Chromium Playwright e Google Chrome chegaram a `https://web.whatsapp.com/` com `cookieEnabled=true` e conexão online.
- Antes do QR, o console do próprio WhatsApp registrou repetidamente `[storage] storage bucket persistence denied (aquire-persistent-storage-denied)`.
- Logo depois, o WhatsApp navegou para `?post_logout=1&logout_reason=0` e exibiu a mensagem de erro no banco de dados do navegador.
- O fluxo antigo ainda podia repetir o Google Chrome em `db_recovery` e terminar sem chegar ao Microsoft Edge.

### Correções
- Antes da primeira navegação, o bot solicita via Chrome DevTools Protocol a permissão web `persistent-storage=granted` (mapeada internamente pelo Chromium para `durableStorage`) exclusivamente para `https://web.whatsapp.com`.
- O diagnóstico passa a registrar `durable_storage_permission_override` e `storage_persistence_denied`.
- `bootstrap_metadata` agora registra `storagePersisted`, estado da permissão `persistent-storage`, disponibilidade de IndexedDB e cota/uso do storage.
- Erro visual de banco do WhatsApp em profile novo não repete mais o mesmo navegador; o fallback avança para o próximo browser em profile inédito.
- A Central passa a classificar esse caso como `WHATSAPP_STORAGE_DENIED`, separando-o de corrupção histórica de profile.

### Compatibilidade
- Base obrigatória do patch: v0.6.0.5.
- Sem alteração de models e sem migration nova.
- Cloudflare/online preservado.
- `robot_ssw` permanece congelado e sem alteração.

## 0.6.0.5 — WhatsApp Web: diagnóstico de bootstrap e fallback por navegador

### Evidência que motivou o patch
- Em profile de pareamento novo, o código abria `https://web.whatsapp.com/`, porém o próprio WhatsApp Web redirecionava antes do QR para `?post_logout=1&logout_reason=0`.
- Isso prova que, nesse cenário, o QR não estava sendo apenas "não capturado": a página de login nem chegava ao estado de QR.
- A v0.6.0.4 só trocava de navegador quando o executável não conseguia abrir. Se o Chromium abria normalmente mas o bootstrap do WhatsApp falhava, o fluxo permanecia preso naquele navegador.

### Correções
- Novo erro explícito `WHATSAPP_POST_LOGOUT` / estado `BOOTSTRAP_LOGOUT`; esse caso não é mais tratado como erro de banco do navegador.
- Detecção de `post_logout` antes da procura do QR.
- Fallback funcional de navegador: **Chromium Playwright → Google Chrome → Microsoft Edge**. O fallback também acontece quando a página abre mas o WhatsApp rejeita o bootstrap.
- Cada tentativa de navegador usa um `browser_profile_pairing_*` inédito. Uma tentativa rejeitada nunca é promovida nem reutilizada.
- Sessão anteriormente promovida que cair em `post_logout` é tratada como sessão revogada e volta para novo pareamento.
- Novo diagnóstico `logs/whatsapp_bootstrap.jsonl`, com eventos de navegação, console warning/error, JavaScript `pageerror`, requests falhas, respostas HTTP >=400 relacionadas ao WhatsApp, abertura/fechamento de WebSocket e metadados básicos do navegador.
- URLs do diagnóstico removem querystrings potencialmente sensíveis e preservam apenas `post_logout`/`logout_reason`; valores longos/tokens são redigidos.
- Central WhatsApp mostra a URL atual do bootstrap e oferece **Baixar diagnóstico do login**.

### Compatibilidade
- Base obrigatória do patch: v0.6.0.4.
- Sem alteração de models e sem migration nova.
- Modo online/Cloudflare da v0.6.0.2 preservado.
- `robot_ssw` permanece congelado e sem alteração.

## 0.6.0.4 — WhatsApp Web: pareamento de dispositivo realmente novo

### Correções
- `Redefinir sessão` invalida a sessão ativa e força novo pareamento.
- Cada pareamento nasce em `browser_profile_pairing_<timestamp>` inédito.
- Profile só é promovido como sessão ativa depois que o WhatsApp realmente conecta.
- Tentativas que falham antes da conexão não viram sessão oficial.
- Para pareamento novo, Chromium Playwright passou a ser priorizado; Chrome e Edge ficaram como fallback de abertura.

### Compatibilidade
- Base obrigatória: v0.6.0.3.
- Sem migration nova.
- `robot_ssw` não alterado.

## 0.6.0.3 — WhatsApp Web: sessão/IndexedDB corrompida e QR Code

### Causa raiz
- O WhatsApp Web pode exibir a mensagem de erro no **banco de dados do navegador** e pedir para parear/reconectar novamente quando o profile persistente/IndexedDB da sessão está corrompido.
- A ação **Redefinir sessão** da v0.6.0.2 usava `shutil.rmtree(..., ignore_errors=True)`. Se Chrome/Edge ainda mantivesse arquivos bloqueados, a limpeza podia falhar silenciosamente e a mesma sessão corrompida era reutilizada.
- O `finally` do processo do bot sempre escrevia `OFFLINE` depois de uma exceção, sobrescrevendo `ERROR` e escondendo a causa real na Central.

### Correções
- Detecção explícita da tela de erro do banco de dados do navegador no WhatsApp Web.
- Auto-reparo único: fecha o contexto, encerra apenas processos que usam o `browser_profile` do bot, isola/remove o profile corrompido, cria um profile novo e abre o WhatsApp novamente para gerar QR.
- **Redefinir sessão** agora confirma que o processo foi encerrado e que o profile foi efetivamente substituído; não há mais `ignore_errors=True` mascarando falha.
- Processos órfãos de Chrome/Edge/Chromium são filtrados pelo caminho do `--user-data-dir` do bot para não encerrar o navegador normal do usuário.
- Estado `ERROR` passa a ser preservado depois que o processo termina, com causa visível na Central.
- Novos estados `SESSION_DB_ERROR` e `REPAIRING_SESSION` para diagnóstico em tempo real.
- Captura do QR foi ampliada para `data-ref`, canvas e SVG, mantendo validação de tamanho/formato para evitar capturas falsas.

### Compatibilidade
- Base obrigatória: v0.6.0.2.
- Sem alteração de models e sem migration nova.
- Cloudflare Quick Tunnel/Waitress da v0.6.0.2 preservados.
- `robot_ssw` homologado permanece 17/17 arquivos idêntico.

## 0.6.0.2 — Cloudflare Quick Tunnel / modo online sem domínio

### Online
- Novo `EXECUTAR_ONLINE.bat` inicia o Painel com Waitress e cria um Cloudflare Quick Tunnel aleatório `*.trycloudflare.com`.
- `cloudflared.exe` é detectado no PATH ou baixado automaticamente da release oficial para `tools/cloudflared`.
- URL pública é capturada dos logs, persistida em `local_data/online_url.txt`, copiada para a área de transferência e aberta no navegador.
- `PANEL_PUBLIC_BASE_URL` passa a receber automaticamente a URL temporária, permitindo que links do Portal do Motorista sejam enviados com endereço acessível externamente.
- Novo `ABRIR_LINK_ONLINE.bat` reabre/copia a URL ativa.
- Novo `PARAR_ONLINE.bat` encerra servidor e túnel.
- Ao voltar para `EXECUTAR_LOCAL.bat`, um túnel iniciado por esta baseline é encerrado para evitar exposição acidental.

### Segurança / servidor
- Modo online usa Waitress ligado somente a `127.0.0.1:8000`; o processo web não escuta diretamente em interfaces públicas.
- Django recebe `ALLOWED_HOSTS` para `*.trycloudflare.com`, `CSRF_TRUSTED_ORIGINS` para HTTPS do Quick Tunnel e reconhecimento de `X-Forwarded-Proto` vindo do proxy local.
- Arquivos de `/media/` continuam disponíveis no modo online por uma rota protegida por login; uploads internos não são publicados anonimamente.
- Novo comando `prepare_online` substitui a senha administrativa padrão antes da primeira publicação pública e salva a credencial gerada apenas em `local_data/ONLINE_ADMIN.txt`.
- `DJANGO_DEBUG=0` e `collectstatic` são aplicados somente ao processo online; o `.env.local` não é sobrescrito.

### Compatibilidade
- Sem migration nova.
- Modo local anterior permanece disponível.
- `robot_ssw` homologado não foi alterado.

## 0.6.0.1 — WhatsApp Web: QR, encerramento e refinamento visual

### Correções
- Central não mostra mais `Offline` apenas por atraso de heartbeat enquanto o processo do bot ainda está aberto.
- Botão **Encerrar bot** permanece disponível sempre que o processo existe, inclusive em estado sem resposta.
- Encerramento ganhou sinal cooperativo e fallback de finalização da árvore do processo/navegador.
- QR Code do WhatsApp Web é capturado e disponibilizado dentro do Painel.
- Bot recarrega a tela de conexão de forma controlada quando o QR não aparece.
- Navegador prefere Chrome/Edge instalados e usa Chromium Playwright como fallback.
- Saída/erro do processo deixa de ir para `DEVNULL` e passa a ser registrada em `logs/whatsapp_bot.log`.
- Nova ação **Redefinir sessão** para remover perfil local preso/corrompido e gerar novo QR.

### UX
- Tela WhatsApp recebeu mais respiro, hierarquia, card de conexão, instruções de QR, prévia da tela do bot e acesso ao log.
- Controles de iniciar/encerrar passam a acompanhar o status em tempo real.

### Compatibilidade
- Patch cumulativo sobre v0.6.0.0.
- Sem migration nova.
- `robot_ssw` homologado não foi alterado.

## 0.6.0.0 — Operação, Portal do Motorista, WhatsApp e Geografia Dinâmica

### Operação e temporalidade
- Rotas passam a distinguir evidência **Confirmada** (saída 85), **Inferida** (outra ocorrência datada do romaneio) e **Planejada** (romaneio sem evidência operacional suficiente).
- Romaneio emitido não é mais apresentado como prova do dia da rota.
- Visão de planejamento permite enxergar romaneios preparados sem afirmar que pertencem ao dia seguinte.

### Motoristas e avaliação
- Ranking separa Qualidade, Produtividade e Confiança da amostra.
- Nota de ranking usa ajuste de confiança em direção à média da equipe para reduzir distorção de amostras pequenas.
- Recuperações validadas geram contribuição pequena e limitada; valor financeiro do frete não vira qualidade.
- Motoristas de teste continuam excluídos dos indicadores oficiais.

### Portal e comprovantes
- Portal mobile mostra rotas, planejamento e oportunidades de retirada.
- Motorista pode fotografar/selecionar comprovante e enviar para validação.
- Coordenador recebe evidência com contexto completo, pode validar, rejeitar ou solicitar nova foto.
- Validação concorrente é protegida por transação/lock; um comprovante não pode ser recuperado duas vezes por cliques simultâneos.

### WhatsApp Bot V1
- Nova Central WhatsApp com motoristas prontos, cadastros pendentes e histórico de envios.
- Envio em lote por operação e envio individual por motorista/romaneio.
- Bot usa WhatsApp Web apenas como canal auxiliar de envio; não lê nem responde conversas.
- Sessão persistente local e status ONLINE/QR/OFFLINE/ERRO.
- Painel e portal continuam funcionando quando o bot está offline.

### Mapa
- Resolução passa a considerar **UF + Município + Bairro**.
- Auto-drill-down pode usar bairros reais presentes na operação mesmo sem provider estático pré-cadastrado.
- Resolvedor dinâmico com cache tenta obter polígonos e preserva fallback textual para bairros não resolvidos.

### Clientes e relatórios
- Cliente pode ser marcado como dependente de comprovante para pagamento.
- Relatórios de operação/comprovantes receberam mais campos operacionais e contexto.

### Compatibilidade
- Patch cumulativo sobre v0.5.0.1.
- Há alterações de models; o launcher local gera/aplica migrations ao primeiro início.
- `robot_ssw` homologado não foi modificado.

## 0.5.0.1 — Correções do levantamento operacional

### Correções
- Ranking de motoristas prioriza amostra elegível; motorista com poucas tentativas não domina o ranking principal apenas por percentual alto.
- Motoristas de teste/homologação podem ser marcados explicitamente e ficam fora de KPIs, médias, rankings, mapa e relatórios oficiais.
- Desempenho médio deixa de cair para zero somente porque nenhum motorista atingiu ainda o mínimo do ranking; elegibilidade continua indicada separadamente.
- Filtros e ordenação da tela de motoristas preservam o período selecionado.
- Clique tanto nos pontos quanto nas datas do eixo do gráfico do Dashboard abre a Operação do Dia.
- Operação do Dia usa o mesmo fallback operacional do mapa para romaneios legados sem ocorrência 85 e permite navegar para rota já preparada.
- Filtro Cidade → Bairro em Clientes passa a ser dependente do município selecionado.
- Mapa mostra nomes/valores das regiões ativas com maior prioridade e, em municípios sem malha de bairros homologada, abre detalhamento regional baseado nos dados SSW em vez de ficar sem resposta.

### UX
- Períodos agora distinguem claramente “Mês atual” de “Últimos 30 dias”.
- Ocorrência 13 passa a ser apresentada como “Horário” nos resumos; ocorrência 34 como “Retenção”.
- Tentativas, Entregas e Entrega limpa receberam nomenclatura/ajuda mais explícita.

### Banco
- Novo campo `Driver.is_test` para identificar registros fictícios/homologação sem heurística por nome. A instalação existente deve executar `makemigrations`/`migrate` ao reiniciar pelo executor local.

### Compatibilidade
- Patch cumulativo sobre a baseline v0.5.0.0.
- Core `robot_ssw` não alterado.

## 0.5.0.0 — Estabilização operacional e evolução analítica

### Correções
- Reconciliação de execuções SSW sem executor/heartbeat, com timeout de despacho e códigos de erro.
- Período preservado na Central de Relatórios e novos períodos móveis, incluindo 30 dias.
- Reconstrução histórica de entregas/comprovantes no corte temporal.
- Alias geográfico para Tapanã/Icoaraci e fallback de clique municipal.
- Ação `Registrar bug` deixa de cobrir paginação.
- Filtro de evidência de comprovantes corrigido.
- Destaque “maior taxa de retenção” passa a ordenar pela taxa, não pelo valor financeiro.

### Evoluções
- Operação do Dia histórica e drill-down do Dashboard.
- Domingo vazio omitido do gráfico; domingo com operação preservado.
- Comprovantes: motorista da retenção x motorista recuperador, submissões/evidências e validação.
- Portal do motorista por token revogável e oportunidades de retirada.
- Avaliação V2 em modo SIMULAÇÃO, separando desempenho e produtividade.
- Perfil de motorista e cliente mais analíticos.
- Central de Relatórios ampliada.
- Caderno de Bugs e Configurações reorganizados.

### Compatibilidade e QA
- Core homologado `robot_ssw` permanece idêntico à v0.4.0.3.
- QA estático/portátil executado; QA Django/runtime deve ser executado na instalação real antes de homologação.

## v0.6.0.4 — WhatsApp: pareamento realmente novo

- Corrige o caso em que o WhatsApp Web continuava apresentando erro de banco/pareamento mesmo após reconstrução do profile.
- `Redefinir sessão` agora invalida a sessão ativa e força o próximo início em um `user-data-dir` inédito.
- Profiles de tentativa não são reutilizados; uma sessão só é promovida como ativa depois de o WhatsApp chegar ao estado conectado.
- Em erro de banco durante a conexão, a recuperação cria outro profile inédito em vez de recriar o mesmo caminho.
- Chromium do Playwright passa a ser a primeira opção de navegador, reduzindo interferência de Chrome/Edge instalados, sync e extensões.
- Novos metadados de diagnóstico: `profile_mode`, `profile_name` e estado `PAIRING_NEW_DEVICE`.
- Sem migrations novas. `robot_ssw` não alterado.

## v0.9.2.0 — estabilização de homologação / navegação rápida (03/09/2026)

- Central de Avaliações passa a considerar oficialmente a Avaliação V3 a partir de **01/09/2026**; ROM13 anterior permanece histórico e não vira fila operacional.
- Remove sincronização ROM13 do GET da Central de Avaliações.
- Formulário ROM13 deixa de expandir dentro da tabela e passa para modal responsivo, corrigindo estouro/corte em 1366×768 e telas menores.
- Dashboard e Comprovantes deixam de recalcular oportunidades no clique.
- Cache Windows muda de LocMem isolado por processo para FileBased compartilhado entre Waitress, scheduler e comandos.
- Reconstrução temporal canônica passa a ser materializada em cache uma vez por versão.
- Matching de Retirada Exata/Ouro reduz o conjunto de comprovantes candidatos antes dos loops em Python.
- Pós-import/startup pré-aquece ranking, KPIs e oportunidades usadas nas telas mais acessadas.
- Nova instrumentação SQL/request e `PERFORMANCE_DIAGNOSTICO.bat` para medir gargalos no banco real.
- `robot_ssw/` permanece congelado e sem alterações.
