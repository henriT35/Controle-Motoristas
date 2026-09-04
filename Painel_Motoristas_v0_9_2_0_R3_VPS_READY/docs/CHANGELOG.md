# Changelog

## 0.9.2.0 — Avaliação V3 explicável, ROM13 manual e retenção pelo estado atual — 2026-09-03

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

---

## 0.4.0.2 — Refinamento visual do Mapa Operacional — 2026-09-01
- refina apenas apresentação/UX do mapa, sem alterar consultas, métricas, geografia, banco ou regras operacionais;
- melhora enquadramento visual e ocupação da área do mapa;
- reduz colisão de labels, priorizando regiões com movimento/maior relevância visual;
- diferencia com mais clareza regiões sem movimento, ativas e em hover;
- adota paleta dark/low-profile menos saturada;
- adiciona legenda compacta dinâmica por métrica, breadcrumb no drill-down e dica discreta de navegação;
- recria tooltip como mini-card operacional com destaque para a métrica selecionada;
- refina ranking, alertas, resumo, painel de detalhe, loading/empty/error states e mapa compacto;
- adiciona cache busting para CSS/JS da versão 0.4.0.2;
- nenhuma migration e nenhum arquivo Python alterado.

## 0.4.0.1 — Hotfix identificação da malha municipal IBGE — 2026-09-01
- corrige mapa municipal vazio apesar de KPIs/ranking carregados;
- a API de Malhas do IBGE identifica feições principalmente por `properties.codarea`; o frontend não deve exigir nome embutido;
- resolve `codarea` para nome oficial usando API de Localidades do IBGE por UF;
- adiciona cache separado para cadastro de municípios e mantém cache de geometria;
- mantém implementação genérica multi-filial, sem hardcode de BEL/CWB;
- amplia aliases de propriedades de nome para provedores de bairros;
- melhora diagnóstico quando a malha existe mas não pôde ser identificada.

## 0.4.0.0 — Mapa Operacional Geográfico V1 — 2026-09-01
- adiciona engine geográfica multi-filial por deployment/unidade ativa, sem hardcode BEL/CWB;
- integra mapa compacto na Operação de Hoje e nova tela Mapa Operacional;
- agrega dados reais por município/bairro a partir de `DeliveryMovement` e ocorrências ROM;
- métricas V1: entregas, retenções, ocorrência 13, comprovantes ativos, entregas limpas, peso e clientes;
- usa data operacional existente (`SAIDA PARA ENTREGA`/código 85) em vez de data de importação;
- mantém separação ROM histórico × CTRC estado consolidado;
- municípios usam malha simplificada oficial do IBGE; bairros de Belém usam provider GeoJSON documentado;
- geometrias e métricas são carregadas separadamente, com cache e payload agregado;
- adiciona detecção conservadora de outliers para não destruir o enquadramento;
- adiciona normalização geográfica/aliases contextualizados e contagem de localização não resolvida;
- remove hardcode de BEL no preflight externo do bridge, comparando `.env SSW_UNIT` com `SSW_ROBOT_UNIT`;
- `robot_ssw/` homologado permanece inalterado;
- documenta limitação V1: a baseline ainda não possui proveniência de filial por movimento para misturar múltiplas unidades na mesma base.


## 0.3.0.10 — 2026-09-01
- Corrige `UNIQUE constraint failed: clients_client.cnpj, clients_client.name` na persistência histórica SSW.
- Troca `Client.bulk_create` das identidades novas por upsert seguro via `get_or_create` e remapeamento das referências em memória.
- Protege promoção de cliente sem CNPJ contra colisão com identidade já consolidada.
- Mantém watchdog/import progress da v0.3.0.9, regra ROM × CTRC da v0.3.0.8 e core homologado do robô intactos.
# 0.3.0.8 — Retenção CTRC / Reconciliação de Comprovantes — 2026-09-01

- separa definitivamente a semântica de ocorrência do ROM (histórico da tentativa) e do CTRC (estado consolidado do documento);
- ROM/CTRC código 34 preserva histórico de retenção, mas somente CTRC atual em 34 mantém o comprovante aberto;
- histórico de 34 + CTRC posterior `1 / ENTREGUE` baixa automaticamente o comprovante em `DATA/HORA OCORR CTRC`;
- `CTe.current_status` passa a ser derivado da trilha `SSW_CTRC`, impedindo ROM posterior de sobrescrever o estado consolidado;
- retenção sem data explícita deixa de usar a data da importação e usa evidência operacional histórica;
- comando `reconcile_ssw_proofs --apply` corrige retroativamente datas falsas e comprovantes que já deveriam estar recuperados;
- recuperações manuais com usuário/motorista têm precedência e nunca são sobrescritas;
- dashboard usa o romaneio como fallback histórico, não o dia da atualização da base;
- nenhuma migration de schema; `robot_ssw/` permanece inalterado.

# 0.3.0.7 — Retry Dispatch Contract — 2026-09-01

- corrige regressão em `dispatch_robot_run()` que rejeitava `priority=True` no botão Reprocessar;
- preserva watchdog, fila pausável e prioridade da janela falha.

# 0.3.0.6 — Windows Status JSON Resilience — 2026-09-01

- corrige `ROBOT_UNEXPECTED` causado por `[WinError 5] Acesso negado` ao substituir `status.json`;
- `status.json` passa a usar temporário exclusivo por PID/thread/UUID em runtime;
- bloqueios transitórios do Windows recebem retry progressivo antes de desistir;
- falha definitiva somente de `status.json` vira warning técnico e não derruba mais a automação SSW;
- `result.json` recebe o mesmo retry, mas continua obrigatório para preservar consistência do resultado final;
- `worker_state.json`, `diagnostic.json`, `environment.json`, `events.jsonl` e `orchestrator.log` passam a ser best-effort;
- proteção é instalada pela bridge do Painel em runtime; o core homologado `robot_ssw/` permanece byte a byte inalterado;
- patch cumulativo: pode ser aplicado em v0.3.0.4 ou v0.3.0.5 e inclui o hotfix do gráfico v0.3.0.5.

# 0.3.0.5 — Dashboard Evolution Hotfix — 2026-09-01

- corrige pico artificial de `Pendências` no último dia da Evolução Operacional;
- movimentos ainda em andamento deixam de ser tratados como pendência documental histórica;
- `Retenções` passa a usar a data real do evento de retenção (código 34 / conferência);
- `Pendências` passa a representar comprovantes retidos ainda abertos, agrupados pela data de origem;
- registros antigos afetados pelo fallback `retained_at=now` são redistribuídos usando a data real da retenção, saída para entrega ou D+1 da emissão;
- Import Engine v2 e fallback legado deixam de gravar a data da importação como data de retenção quando o SSW não informa `DATA OCORR`;
- eixo X do gráfico passa a mostrar `dd/mm`, eliminando ambiguidade entre fim de um mês e início do seguinte;
- entregas são deduplicadas por CT-e/dia na série histórica;
- core homologado `robot_ssw/` não foi alterado.

# 0.3.0.4 — Robot Resilience & Diagnostics — 2026-09-01

- watchdog externo ao core homologado, com timeout duro e heartbeat;
- Chromium/Playwright passa a nascer dentro do processo protegido, não no request Django;
- diagnóstico por `execution_id`: events, orchestrator, worker process/state, environment e diagnostic;
- código real de erro (`DOWNLOAD_TIMEOUT`, `AUTH_OR_OPTION_TIMEOUT` etc.) preservado mesmo quando o processo filho sai não-zero;
- kill da árvore worker/browser em timeout;
- fila pausa após falhas externas para evitar cascata e reprocessamento do lote;
- dispatch e scheduler respeitam a pausa;
- reconciliação de jobs zumbis `DISPATCHED/RUNNING` via PID + heartbeat;
- histórico permite baixar diagnóstico e reprocessar somente a janela que falhou;
- retry da janela falha recebe prioridade e não recria as janelas concluídas;
- modo Celery usa o mesmo watchdog e não faz autoretry cego;
- core homologado `robot_ssw/` preservado byte a byte (17/17 arquivos da baseline; manifesto 6/6).

# 0.3.0.3 — QA Hardening — 2026-08-31

- serialização cross-processo da aplicação SSW para impedir corrida entre upload manual e worker do robô;
- lock de fila para impedir jobs ativos duplicados por duplo clique/duas abas;
- identidade semântica de ocorrência normaliza descrição antes da deduplicação;
- validação de números/datas/horas inválidos deixa de converter silenciosamente dados ruins para zero/None no Engine v2;
- arquivos inválidos que falham antes do parser agora deixam ImportRun ERROR rastreável;
- ImportRun MANUAL interrompido por restart é reconciliado no próximo bootstrap local;
- testes extremos de reimportação 10x, rename, shuffle, linha duplicada, recuperação manual e CNPJ;
- comandos `qa_import_idempotency` (rollback seguro) e `qa_ssw_integrity` (somente leitura);
- core homologado do robô permanece 6/6 hashes idênticos.

# 0.3.0.2 — Import Turbo — 2026-08-31

- telemetria de importação fora da transação SQLite;
- progresso real por fase no navegador;
- menos SELECTs/reloads no Import Engine v2;
- uma única leitura do histórico de ocorrências afetado;
- pré-carga de endereços restrita ao lote;
- ocorrência/retenção/saída de rota derivadas em um único passe;
- períodos >31 dias quebrados mensalmente para qualquer tipo de solicitação;
- core Playwright homologado permanece intocado.

# 0.3.0 — Performance & Stability — 2026-08-31
- Import Engine v2 adicionado com preload, comparação em memória, `bulk_create`, `bulk_update` e `transaction.atomic`.
- Engine v2 é padrão; rollback temporário disponível com `SSW_IMPORT_ENGINE=v1`.
- Timings e contagens de linhas adicionados ao `ImportRun`.
- Operação de Hoje passou a carregar comprovantes abertos uma vez por visão, não uma vez por romaneio.
- Movimentos carregados para os cards são reutilizados nos KPIs e cobertura por bairro.
- Perfil do motorista deixou de executar 12 consultas mensais independentes.
- Clientes usa Prefetch filtrado para recuperações e elimina N+1.
- KPIs de comprovantes consolidados em aggregate único.
- Histórico SSW calcula duração média no banco.
- `SystemSettings` recebe cache local curto com invalidação em save/delete.
- Caderno de Bugs recebe paginação server-side de 50 itens.
- ECharts recebe registry central e resize com debounce; polling de importação ajustado para 1,2s.
- Inicialização Windows executa `makemigrations` apenas quando o hash dos models muda.
- Logging com rotação e novos índices direcionados a ocorrências, comprovantes, importações e relatórios.
- Adicionados `healthcheck`, `benchmark_system` e `benchmark_ssw_import`.
- Workload CPU de normalização na amostra de 2.838 linhas reduziu média de 0,121342s para 0,034212s no ambiente de construção (71,80%).
- Core homologado do Robô SSW preservado 6/6 hashes.

# 0.2.2-p13.3 — Pacote completo consolidado — 2026-08-31
- Distribuição completa que incorpora p13, p13.1, p13.2 e p13.3; não exige aplicação dos patches antigos.
- Core original homologado da opção 036 incluído e validado pelo manifesto SHA-256 (6/6 arquivos).
- `apps/ssw/robot_bridge.py` consolidado com `BRIDGE_BUILD = 0.2.2-p13.3`.
- Removido do caminho ativo o bridge/adapter experimental que gerava “Nenhum robô real foi encontrado”.
- Preparador robusto do robô incluído com `playwright` + `python-dotenv` e instalação do Chromium.
- Scripts de teste por etapa incluídos: login, opção 036, formulário e download.
- `VERIFICAR_BRIDGE_P13.bat` incluído para provar qual integração o Django está carregando.
- Pacote final limpo de banco local, `.venv`, `.env.local`, `.env` do robô, mídia, logs e caches.

# 0.2.2-p13 — Integração do Robô SSW Homologado — 2026-08-31
- Restaurado como executor principal o pacote original homologado da opção 036.
- Core Playwright preservado byte a byte; manifesto `HOMOLOGATED_CORE.sha256` adicionado.
- API oficial do executor: `robot_ssw.run_job(payload, status_callback)`.
- Removidas do caminho ativo as heurísticas experimentais de login/PLAY dos patches p10/p12.
- Painel passa a adaptar somente payload, callback, `ImportRun`, `ImportStep` e fronteira `DOWNLOADED → VALIDATING`.
- `DOWNLOADED` não é tratado como sucesso final; `SUCCESS/WARNING` só ocorre após o importador aplicar os dados.
- Preflight valida core, `run_job`, `.env`, Playwright, Chromium e permissão da pasta de saída, sem fazer login real.
- Credenciais p11/p12 são migradas para o `.env` esperado pelo core homologado; nunca entram no job.
- Execução local permanece silenciosa via `manage.py run_ssw_robot <run_id>` e `CREATE_NO_WINDOW` no Windows.
- Diagnósticos por etapas adicionados: login, opção 036, formulário e download real.
- Teste contratual isolado prova `► → 036+Enter → expect_popup → S/BEL/DDMMAA → #btn_env_periodo.click → download` sem alterar o core.

# 0.2.2-p5 — bateria e robustez do robô
- Adapter SSW agora respeita status de erro retornado pelo robô e não aceita arquivo parcial como sucesso.
- Compatibilidade adicionada para entrypoints `**kwargs`.
- Sanitização de senha aplicada a stdout/stderr, mensagens de erro e traceback do adapter.
- Diagnóstico diferencia adapter presente de robô Playwright real presente.
- Adicionado `TESTAR_ROBO_BATERIA.bat` e relatório de QA.

# Changelog

## 0.2.2-p4 — 2026-08-31
- Credenciais do SSW padronizadas em `robot_ssw/credenciais.local.json`.
- Novo `CONFIGURAR_CREDENCIAIS_SSW.bat` solicita usuário/senha uma única vez.
- Senha é digitada de forma oculta no terminal; arquivo local real é ignorado pelo Git e não entra nos pacotes.
- `painel_adapter.py` carrega as credenciais somente dentro do processo do robô e fornece variáveis `SSW_*` / `ROBO_SSW_*`.
- `TESTAR_CREDENCIAIS_SSW.bat` valida a configuração sem exibir a senha.
- Credenciais continuam fora de `task.json`, banco e logs do Painel.

## 0.2.2-p3 — 2026-08-31
- Bridge real Painel Motoristas ↔ Robô SSW adicionado.
- Solicitações passam por `QUEUED → DISPATCHED → RUNNING → SUCCESS/WARNING/ERROR`.
- Contrato por `task.json` com período, `execution_id`, unidade BEL, opção 036, Excel=S e pasta isolada por execução.
- Retorno do robô aceito por `result.json`/arquivo em `download_dir`; arquivo segue para o importador idempotente sem criar um segundo ImportRun.
- Execução local assíncrona via processo separado e opção de despacho via Celery.
- Importações históricas são serializadas: apenas uma sessão do robô por vez.
- Falha do robô interrompe continuação automática da fila para evitar repetição massiva de erro de login/selector.
- Adapter genérico `robot_ssw/painel_adapter.py`, diagnóstico `TESTAR_INTEGRACAO_ROBO_SSW.bat` e controles de habilitar/desabilitar adicionados.
- Credenciais continuam fora do contrato do Painel e permanecem configuradas no próprio robô.
- Tela de Importações passa a exibir se o bridge do robô está habilitado.

## 0.2.2-p2 — 2026-08-31
- BUG-0001: importação SSW ganhou feedback ao vivo durante upload e processamento, com barra de progresso, estágio corrente, arquivo e tempo decorrido.
- Novo endpoint autenticado `/ssw/importacoes/progresso/` para acompanhamento leve da execução manual.
- BUG-0002: `Operação de Hoje` passou a considerar carry-over de rotas recentes que continuam em `SAIDA PARA ENTREGA`, cobrindo o cenário 29/08 → 31/08 (virada de fim de semana).
- Carry-over só permanece quando a ocorrência mais recente antes do dia ainda é `SAIDA PARA ENTREGA`; uma ocorrência posterior antes do dia encerra a continuidade.
- `Disponíveis hoje` no Dashboard agora é calculado pelas oportunidades da data atual, inclusive para comprovantes retidos em períodos anteriores.
- Valores financeiros do Dashboard receberam formatação executiva pt-BR (`R$ 3,02 mi`, `R$ 426,8 mil`) com valor exato em tooltip.
- Peso do Dashboard passa a usar separador de milhar pt-BR.
- Testes adicionados para carry-over de fim de semana, encerramento do carry-over, entrega durante o dia-alvo, endpoint de progresso e formatação financeira.

## 0.2.2-p1 — 2026-08-31
- Patch de troca do Caderno de Bugs.
- Botão **Exportar Caderno** gera ZIP com `BUGS.md`, `bugs.json`, `resumo.json`, `LEIA-ME.txt` e `prints/`.
- Botão **Importar Caderno** reimporta/mescla o ZIP sem duplicar registros.
- `sync_id` UUID permanente adicionado aos bugs para conciliação entre máquinas/pacotes.
- Importação transacional com limites de tamanho e proteção contra path traversal.
- Auditoria `BUG_NOTEBOOK_EXPORTED` / `BUG_NOTEBOOK_IMPORTED`.
- Testes automatizados de exportação, reimportação e rejeição de ZIP inválido.

## 0.2.2 — 2026-08-31
- Caderno de Bugs adicionado dentro do próprio Painel Motoristas (`/bugs/`).
- Registro por tela com prioridade P0–P3, status, descrição, atual/esperado, reprodução, correção e reteste.
- Upload de print/anexo de evidência com limite de 8 MB.
- Filtros, KPIs, painel de detalhes e edição de bugs.
- Atalho contextual “Registrar bug” nas telas internas para staff/admin.
- Auditoria `BUG_CREATED` / `BUG_UPDATED`.
- Mídia local configurada para evidências de homologação.
- Captura Playwright ampliada para 12 telas, incluindo o Caderno de Bugs.
- Documentação adicionada em `BUG_NOTEBOOK.md` e `RELATORIO_CORRECOES_V0_2_2.md`.

## 0.2.1 — 2026-08-31
- Operação de Hoje passa a usar `SAIDA PARA ENTREGA` (código 85) como data operacional, separada da emissão do romaneio.
- Dashboard, Motoristas, Clientes e Relatórios alinhados ao período operacional.
- Histórico da rota preservado após `ENTREGUE`.
- Importação fora de ordem protegida contra regressão de status de CT-e/romaneio.
- Retenção histórica mais antiga pode corrigir data/origem do comprovante sem duplicação.
- CNPJ/CPF/CEP normalizados para match e identidade; duplicidades óbvias de clientes reduzidas.
- Recuperação de comprovante valida datas e criticidade default passa a ser estritamente maior que 15 dias.
- Oportunidades de retirada consolidadas por comprovante único.
- Importação de vários meses adicionada via `IMPORTAR_LOTE_SSW.bat`, comando `import_ssw_batch` e upload múltiplo.
- Responsividade/sidebar mobile aprimorada.
- Testes automatizados ampliados para as regras acima.
- Fechamento documentado em `BUGS_RODADA_01.md` e `RELATORIO_CORRECOES_V0_2_1.md`.

## 0.2.0 — 2026-08-31
- Grande rodada de correção visual e funcional baseada na homologação e mockups aprovados.
- Dashboard, Operação de Hoje, Motoristas, Perfil, Comprovantes, Clientes, Relatórios, Importações, Histórico SSW e Configurações revisados.
- Score, regras de entrega, oportunidades de retirada, auditoria, XLSX/PDF e configurações persistentes implementados.
- Robô SSW real permanece explicitamente pendente de integração externa.
- Fechamento do pacote: duração de ImportRun corrigida, inicialização local otimizada e testes locais ampliados.

## 0.3.0.9 — Watchdog por domínio
- Separa timeout do robô (900s padrão) do Import Engine (3600s padrão).
- Após DOWNLOADED, acompanha progresso real do importador em vez de permanecer no estágio do robô.
- Adiciona códigos IMPORT_HARD_TIMEOUT e IMPORT_ENGINE_ERROR.
- Preserva `robot_ssw/` homologado.
