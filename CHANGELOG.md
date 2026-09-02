# Changelog

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
