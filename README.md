> Baseline atual: **v0.7.1.1**

# Painel Motoristas — v0.7.1.1


## v0.7.1.1 — correção do instalador Baileys no Windows

A v0.7.1.0 baixava o Node portátil corretamente, mas os scripts internos executados pelo `npm install` não encontravam o comando `node` porque `tools\node` não era colocado no `PATH`. O hotfix v0.7.1.1 corrige a herança do `PATH`, valida `node.exe` pelo shell antes da instalação e limpa com segurança um `node_modules` parcial deixado pela tentativa anterior.

Se a instalação anterior falhou com **`'node' não é reconhecido`**, aplique a v0.7.1.1 e rode novamente `INSTALAR_BOT_WHATSAPP.bat`. Não é necessário apagar manualmente o Node portátil.

## v0.7.1.0 — WhatsApp Baileys / Node.js

O login antigo do WhatsApp baseado em navegador foi aposentado. **Chrome/Edge, Playwright, CDP, profile de navegador, IndexedDB e captura de tela não participam mais do pareamento oficial.**

O fluxo atual é:

`Painel Django → serviço Node.js → Baileys → QR direto → tela Conectar WhatsApp`

O Baileys trabalha diretamente com o protocolo multi-dispositivo do WhatsApp por WebSocket. Quando o evento de conexão entrega um `qr`, o serviço Node gera `local_data/whatsapp/qr.png`; o Django apenas exibe essa imagem. A sessão criptográfica fica em `local_data/whatsapp/baileys_auth/` e não entra no ZIP.

### Preparação no Windows

1. Execute `INSTALAR_BOT_WHATSAPP.bat` **uma vez**.
2. O instalador usa Node.js 20+ já existente ou baixa **Node.js 24 LTS portátil** para `tools/node/`.
3. O instalador executa `npm install` dentro de `whatsapp_bridge/`.
4. Abra **WhatsApp Motoristas → Conectar / QR Code**.
5. Clique **Novo pareamento** se quiser descartar uma sessão anterior.
6. Clique **Gerar QR Code**.
7. No celular: WhatsApp → Aparelhos conectados → Conectar um aparelho.

Se já existir uma sessão Baileys válida, o serviço conecta sem pedir novo QR.

### Envio

A fila continua no Django (`WhatsAppMessage`). O bridge Node consulta uma API interna vinculada a `127.0.0.1` e protegida por token aleatório local, envia a mensagem com `sock.sendMessage()` e devolve o resultado ao Django. O serviço **não registra listener de `messages.upsert`** e não implementa leitura/resposta automática de conversas.

### Observação importante

Baileys é uma integração **não oficial** e pode exigir atualização quando o WhatsApp alterar o protocolo. O restante do Painel e o Portal do Motorista continuam independentes do WhatsApp.


## v0.8.0.0 — VPS Hostinger / GitHub / automação 24h

A baseline v0.8.0.0 está preparada para rodar integralmente em uma VPS Ubuntu da Hostinger por Docker Compose, inicialmente **sem domínio**, acessando `http://IP_PUBLICO_DA_VPS`. O deploy oficial passa a ser GitHub → `git clone` → `.env` → `docker compose up -d --build`.

Serviços: Nginx, Django/Gunicorn, PostgreSQL, Redis, Celery Worker, Celery Beat, worker SSW Playwright e WhatsApp Baileys. Todos usam restart automático; dados/sessões ficam em volumes persistentes.

### Automação SSW

Na tela **SSW → Importações e Sincronização** é possível ativar/desativar a automação, definir o intervalo em minutos (mínimo 15) e usar **Atualizar agora** sem esperar o próximo ciclo. O scheduler consulta a configuração a cada minuto e o robô roda em fila exclusiva, com um job por vez.

### WhatsApp

A Central possui **Gerar e enviar para todos**, edição de telefone de qualquer motorista e resolução automática de números brasileiros com/sem o nono dígito. O Baileys continua sem leitura automática de conversas.

### Deploy

Leia `docs/VPS_HOSTINGER_GITHUB.md`. Arquivos principais: `docker-compose.yml`, `.env.vps.example`, `deploy/vps/install.sh`, `deploy/vps/update.sh` e `deploy/vps/status.sh`.

> O acesso por IP puro está configurado em HTTP porque não há domínio. Funciona como etapa inicial, porém os links do Portal contêm tokens; HTTPS é recomendado para endurecimento posterior.

## v0.7.0.0 — Operação, temporalidade e Entregas Gerais

> Histórico: o mecanismo de WhatsApp descrito nesta seção foi **substituído integralmente na v0.7.1.0 pelo Baileys/Node.js**. Ele não faz parte do fluxo ativo atual.

Esta versão corrige a causa que fazia romaneios antigos reaparecerem em dias recentes. A data operacional agora é canônica por romaneio: ocorrência 85 datada confirma a rota; sem 85, o primeiro fato ROMANEIO datado pode inferir; sem evidência, o romaneio fica em planejamento/data não confirmada. Emissão, importação e CTRC consolidado não viram data de rota.

Também foram adicionados **Entregas Gerais**, ficha clicável do CT-e, KPI **Retidos no dia**, persistência de filtros/contexto pelo menu lateral e fallback do Mapa quando não existem polígonos de bairro.

Nesta mesma baseline, dois bugs bloqueadores de uso móvel foram incorporados à rodada: o Portal agora possui ações separadas **Tirar foto** e **Escolher arquivo/PDF**, e o pareamento do WhatsApp foi refeito para abrir Chrome/Edge como navegador normal e mostrar o QR em uma **tela dedicada do Painel**. O Playwright apenas se conecta depois via CDP local para capturar o QR e operar a sessão.

Fluxos principais para homologação:

1. Dashboard → clicar em uma data → conferir a mesma fotografia na Operação do Dia.
2. Operação → Rota → CT-e → Detalhe → Voltar sem perder a rota/data.
3. Entregas Gerais → aplicar filtros → trocar de módulo → voltar pelo menu e confirmar o estado preservado.
4. Abrir município sem polígonos: os dados devem continuar em lista/ranking, sem overlay bloqueante.

Não há migration nova. `robot_ssw` não foi alterado. A homologação real em Windows/Django/banco continua obrigatória antes de promover a versão para produção.

## v0.6.0.6 — correção do armazenamento do WhatsApp antes do QR

O diagnóstico real da v0.6.0.5 identificou a falha antes do QR: o próprio WhatsApp Web registrava `storage bucket persistence denied` e em seguida navegava para `post_logout=1&logout_reason=0`, mesmo usando profiles inéditos. A v0.6.0.6 concede ao origin do WhatsApp a permissão `persistent-storage` via DevTools Protocol (mapeada pelo Chromium para `durableStorage`) antes de abrir a página e registra no diagnóstico se o storage ficou persistente.

Se um navegador ainda recusar o storage, o bot avança para o próximo navegador em vez de repetir a mesma tentativa.

Fluxo de teste: **Encerrar bot → Redefinir sessão → Conectar WhatsApp → verificar QR**. Se ainda falhar, baixar novamente `whatsapp_bootstrap.jsonl`; procure pelos eventos `durable_storage_permission_override`, `bootstrap_metadata` e `storage_persistence_denied`.

## v0.6.0.5 — WhatsApp: `post_logout` antes do QR

Esta versão ataca especificamente o caso em que o navegador abre `https://web.whatsapp.com/`, mas o próprio WhatsApp redireciona para `?post_logout=1&logout_reason=0` antes de gerar o QR. O bot agora diferencia esse evento de erro de IndexedDB, tenta outro navegador em um profile totalmente novo e grava um diagnóstico de bootstrap em `logs/whatsapp_bootstrap.jsonl`. Na Central WhatsApp, use **Baixar diagnóstico do login** caso todas as tentativas falhem.

Ordem de tentativa durante novo pareamento: Chromium Playwright → Google Chrome → Microsoft Edge. Cada tentativa nasce em um user-data-dir separado e só é persistida se realmente conectar.

Baseline completa candidata à homologação do Painel Motoristas. Esta versão consolida a estabilização da orquestração SSW, histórico operacional, comprovantes, avaliação V2 dos motoristas, clientes, relatórios, Dashboard, mapa e Caderno de Bugs.

> **Importante:** o pacote passou no QA estático/portátil disponível no ambiente de empacotamento, mas o ambiente não possui Django instalado. Antes de homologar para uso real, execute `VERIFICAR_BUILD.bat` na instalação Windows com a `.venv` preparada e teste migrations/upgrade em banco de homologação.

## Começar no Windows

1. Extraia o ZIP numa pasta nova.
2. Copie/configure apenas as credenciais locais conforme `PRIMEIROS_PASSOS.txt` e `docs/CREDENCIAIS_ROBO_SSW.md`.
3. Execute `EXECUTAR_LOCAL.bat` em ambiente de homologação para preparar/aplicar o schema local.
4. Execute `VERIFICAR_BUILD.bat`.
5. Só depois substitua a baseline anterior.

O pacote não inclui banco real, `.env`, credenciais, downloads, logs nem `.venv`.





## v0.6.0.3 — correção do QR / banco de dados do navegador do WhatsApp

Se o WhatsApp Web abrir pedindo para reconectar e mostrar erro no **banco de dados do navegador**, a sessão local do bot é tratada como corrompida. O bot tenta reconstruí-la automaticamente uma vez e abrir uma sessão limpa para gerar um novo QR Code.

A ação **Redefinir sessão** também foi endurecida: ela não informa sucesso se o profile continuar bloqueado. Processos órfãos são encerrados somente quando usam o `browser_profile` exclusivo do bot, preservando o Chrome/Edge normal do usuário. Erros reais do bot permanecem visíveis na Central em vez de serem apagados por um estado `OFFLINE`.

Fluxo esperado após atualizar:

1. Abra **WhatsApp Motoristas**.
2. Clique **Redefinir sessão** uma vez para eliminar o profile corrompido herdado.
3. Clique **Conectar WhatsApp**.
4. O bot deve abrir uma sessão limpa e o QR deve aparecer na Central/janela do WhatsApp Web.
5. Se o próprio WhatsApp detectar a corrupção durante a abertura, o auto-reparo é executado uma vez sem intervenção.

## v0.6.0.2 — Modo online sem domínio

Esta baseline adiciona publicação temporária pela Internet usando **Cloudflare Quick Tunnel**, sem domínio próprio e sem abrir portas no roteador.

### Uso no Windows

1. Execute `EXECUTAR_ONLINE.bat`.
2. Na primeira execução o launcher baixa o `cloudflared.exe` oficial para `tools\cloudflared` se ele ainda não existir.
3. O launcher cria uma URL aleatória `https://...trycloudflare.com`, configura essa URL como `PANEL_PUBLIC_BASE_URL` do processo online e abre o login no navegador.
4. A URL atual também fica em `local_data\online_url.txt`; `ABRIR_LINK_ONLINE.bat` abre/copia o endereço novamente.
5. Para encerrar **Painel + túnel**, use `PARAR_ONLINE.bat`.

O modo online usa **Waitress** em `127.0.0.1:8000`; o Django não é exposto diretamente na rede. O Quick Tunnel aponta para esse endereço local. A URL é temporária e normalmente muda quando o túnel é recriado.

### Proteção da conta administrativa

Se a conta `admin` ainda estiver com a senha local padrão `Painel@2026!`, o primeiro início online substitui essa senha por uma credencial aleatória forte. A credencial gerada fica somente no computador, em `local_data\ONLINE_ADMIN.txt`. Se a senha já foi personalizada, ela é preservada.

### WhatsApp / Portal

O endereço `trycloudflare.com` capturado pelo launcher passa automaticamente a ser a base pública dos links enviados aos motoristas. Assim o Portal do Motorista deixa de gerar links `localhost` quando o Painel está no modo online.

> O Quick Tunnel é uma solução temporária de acesso público. Não há URL fixa sem domínio.

## Correção v0.6.0.1 — conexão do WhatsApp Web

- QR Code passa a ser capturado pelo bot e exibido também dentro da Central WhatsApp.
- O bot tenta usar Google Chrome ou Microsoft Edge instalados antes do Chromium do Playwright, melhorando compatibilidade com o WhatsApp Web.
- Heartbeat não transforma mais um processo aberto em “Offline” silenciosamente; processo travado aparece como **Bot sem resposta** e continua podendo ser encerrado.
- **Encerrar bot** usa parada cooperativa e, se necessário, finaliza a árvore do processo/navegador.
- Nova ação **Redefinir sessão** remove apenas o perfil local do WhatsApp para forçar um QR novo.
- Nova prévia **Ver o que o bot está enxergando** e download do log técnico.
- Central WhatsApp recebeu mais espaçamento, hierarquia visual e um card dedicado para conexão/QR.


## Novidades da v0.6.0.0

- Central **WhatsApp dos Motoristas** para conectar o WhatsApp Web da empresa e enviar links em lote ou por romaneio.
- Portal mobile com rota, oportunidades de retirada e envio de foto/PDF para validação.
- Coordenador valida comprovantes com contexto completo e pode pedir nova foto.
- Operação do Dia separa rota confirmada, inferida e planejamento sem inventar a data pela emissão.
- Avaliação separa Qualidade, Produtividade e Confiança; amostras pequenas não dominam o ranking.
- Mapa resolve bairros no contexto UF + município e tenta carregar apenas bairros presentes na operação.

### Preparar o WhatsApp (arquitetura local; na VPS o serviço sobe automaticamente)

1. Execute `INSTALAR_BOT_WHATSAPP.bat` uma vez.
2. O instalador prepara Node.js 20+ e `whatsapp_bridge/node_modules`.
3. Abra **WhatsApp Motoristas → Conectar / QR Code**.
4. Clique **Gerar QR Code**.
5. O QR é gerado diretamente pelo Baileys; nenhum Chrome/Edge é aberto.
6. Escaneie pelo celular em **Aparelhos conectados**.

A sessão fica em `local_data/whatsapp/baileys_auth/`. Use **Novo pareamento** apenas quando quiser descartar essa sessão e vincular o aparelho novamente.


## Patch v0.5.0.1

Correções cumulativas sobre a v0.5.0.0 para ranking/amostra de motoristas, registros de teste, clique no gráfico do Dashboard, reconstrução da Operação do Dia, filtros Cidade → Bairro e comportamento do Mapa em municípios sem malha de bairros homologada. Consulte `docs/PATCH_V0_5_0_1.md`.

## O que mudou na v0.5.0.0

### Robô SSW e fila
- Timeout específico para tarefa despachada que nenhum executor assume.
- Detecção de processo perdido, heartbeat perdido e jobs órfãos.
- Reconciliação também pelo polling da interface.
- Fila é liberada/pausada com diagnóstico em vez de ficar eternamente carregando.
- O core homologado `robot_ssw/robot_ssw` **não foi alterado**.

### Operação do Dia
- `/operacao/hoje/?date=AAAA-MM-DD` permite consultar operação histórica.
- Entregas e comprovantes respeitam o corte temporal da data consultada.
- O fim do dia não precisa apagar a fotografia operacional da rota.

### Dashboard
- Domingo sem operação é omitido do gráfico; domingo com movimento permanece.
- Pontos do gráfico são clicáveis e abrem a Operação do Dia com foco na série.
- Períodos móveis incluem 7d/30d/60d/90d.
- KPIs históricos de comprovantes usam o estado existente no fechamento do período.

### Motoristas
- Perfil V2 com período e mais indicadores.
- **Produtividade** separada de **Desempenho**.
- Retenção atribuída à tentativa usa ROM34; comprovante ativo é indicador separado.
- Nota V2 permanece explicitamente em **SIMULAÇÃO** e mostra breakdown “Por que esta nota?”.
- Indicador de comprovantes resgatados e confiança de amostra.

### Comprovantes
- Motorista da retenção e motorista recuperador são fatos distintos.
- Registro manual de recuperação com motorista explícito, data, observação e evidência opcional.
- Submissões do portal aguardam validação; upload não encerra comprovante automaticamente.
- Filtros por período, status, idade, motoristas, região, SLA e evidência.
- Idade histórica usa a data do corte, nunca a data de importação.

### Portal do motorista
- Acesso por token aleatório, revogável e regenerável, sem CPF/ID sequencial na URL.
- Mostra rota/oportunidades de retirada relacionadas ao motorista.
- Permite enviar evidência para validação do coordenador.

### Clientes e Relatórios
- Clientes ganharam filtros temporais e visão analítica.
- Relatórios preservam o período selecionado em preview/PDF/XLSX.
- Relatórios ampliados para motoristas, comprovantes, clientes e operação diária.
- Financeiro usa somente campos realmente persistidos; não inventa status financeiro.

### Mapa Operacional
- Alias para variações como `TAPANA (ICOARACI)` → `TAPANA`.
- Município sem malha de bairros recebe detalhe/fallback em vez de clique silencioso.
- Comprovantes no mapa respeitam o corte histórico.
- O visual premium/low-profile da v0.4.0.3 foi preservado.

### Caderno de Bugs / Configurações
- `Registrar bug` foi integrado ao header para não cobrir paginação.
- Bug pode registrar causa raiz, resolução, reteste e versão corrigida.
- Configurações foram reorganizadas por domínio.

## Regras operacionais críticas

### ROM x CTRC
- `ROM 34` registra retenção histórica naquela tentativa/romaneio.
- `CTRC 34` representa o estado consolidado observado como retido no relatório.
- Um estado CTRC posterior `ENTREGUE` encerra a retenção ativa de origem SSW na data operacional da entrega.
- Isso **não** identifica automaticamente quem recuperou fisicamente o comprovante.
- Recuperação manual/validada mantém `recovery_driver`, evidência e auditoria separados do motorista da retenção.

### Data operacional
A data de importação nunca substitui a data de negócio. A rota prefere ocorrência 85 `SAIDA PARA ENTREGA`; retenção usa sua ocorrência/data operacional real.

### Idempotência
Reimportação não deve multiplicar CT-es, clientes, ocorrências, rotas ou comprovantes. A identidade de novos clientes usa upsert seguro no conjunto deduplicado do lote, fora do loop quente por linha.

## QA e documentação

Leia primeiro:
- `docs/RELATORIO_FINAL_V0_5_0_0.md`
- `docs/AUDITORIA_PRE_IMPLEMENTACAO.md`
- `docs/BUGS_CAUSA_RAIZ.md`
- `docs/QA_RELEASE.md`
- `docs/OPERACAO_DIARIA.md`
- `docs/AVALIACAO_MOTORISTAS.md`
- `docs/COMPROVANTES.md`
- `docs/PORTAL_MOTORISTA.md`
- `docs/CLIENTES.md`
- `docs/RELATORIOS.md`
- `docs/DASHBOARD.md`
- `docs/MAPA_OPERACIONAL.md`
- `docs/CADERNO_BUGS.md`
- `CHANGELOG.md`

## Limitação geográfica conhecida
A engine é multi-região, mas movimentos históricos ainda não carregam proveniência de filial suficiente para misturar várias filiais na mesma base e separá-las historicamente com segurança. A unidade ativa continua sendo uma configuração da instalação.
