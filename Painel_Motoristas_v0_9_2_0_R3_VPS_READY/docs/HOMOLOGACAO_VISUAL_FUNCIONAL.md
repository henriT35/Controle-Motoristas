> **Regra superada na v0.3.0.8:** a validação do relatório real 036 mostrou que ROM e CTRC têm papéis distintos. Histórico ROM=34 + CTRC posterior 1/ENTREGUE representa baixa automática; recuperação manual continua soberana.

# HOMOLOGAÇÃO VISUAL E FUNCIONAL — PAINEL MOTORISTAS

**Versão auditada:** V0.1.2 Local sem Docker  
**Data da auditoria:** 31/08/2026  
**Tipo:** auditoria inicial, antes das correções  
**Referências:** `docs/PROMPT_MESTRE.md` + 11 mockups em `docs/mockups/`

> Regra desta rodada: primeiro auditar e documentar. Nenhuma correção de interface/código foi aplicada durante esta auditoria.

---

## 1. Resumo executivo

A V0.1.2 é uma **fundação funcional**, mas ainda não corresponde ao produto visual e operacional aprovado nos mockups. Todas as telas principais possuem algum template, porém várias funcionam hoje como estrutura mínima, com indicadores ausentes, ações sem backend, dados decorativos/hardcoded ou áreas explicitamente marcadas como futuras.

O principal diagnóstico é:

- a base Django e os modelos centrais existem;
- o parser do relatório real do SSW reconhece corretamente a estrutura do arquivo e a regra de retenção;
- o design system inicial existe, mas a composição dos mockups ainda não foi reproduzida em profundidade;
- várias telas ainda não possuem as funções que a interface visual promete;
- o score executivo ainda não existe;
- cruzamento de rota com comprovante retido ainda não existe;
- geração de PDF/XLSX ainda não existe;
- configurações não persistem;
- permissões por perfil ainda não existem;
- automação real do robô SSW ainda é apenas um ponto de integração;
- não existem testes automatizados no repositório.

### Dashboard de homologação preliminar

| Indicador | Resultado |
|---|---:|
| P0 — bloqueadores confirmados | 0 |
| P1 — críticos | 19 |
| P2 — importantes | 12 |
| P3 — polimento | 4 |
| Mockups catalogados | 11/11 |
| Templates principais existentes | 11/11 |
| Telas visualmente homologadas | 0 |
| Testes automatizados encontrados | 0 |
| Python — compilação estática | PASS |
| Parser SSW — arquivo real | PASS |
| Django runtime neste ambiente de auditoria | NÃO EXECUTADO |
| Playwright/screenshots automáticos | NÃO EXECUTADO |

**Motivo da limitação de runtime:** o ambiente de auditoria não possui Django instalado e não possui acesso externo para instalar dependências. O usuário já confirmou que a V0.1.2 executa no Windows local; nesta rodada foi possível realizar auditoria estática completa do projeto, dos mockups e teste isolado do parser SSW.

---

## 2. Ambiente e evidências verificadas

### Mockups

Todos os 11 mockups oficiais existem em `docs/mockups/` e possuem **1672 × 941 px**, exatamente a resolução de referência especificada.

Arquivos:

- `login.png`
- `dashboard.png`
- `operacao_hoje.png`
- `motoristas.png`
- `perfil_motorista.png`
- `comprovantes_retidos.png`
- `clientes.png`
- `relatorios.png`
- `importacoes_ssw.png`
- `historico_robo_ssw.png`
- `configuracoes.png`

### Código Python

`compileall` e parsing AST foram executados sobre o código Python do projeto.

**Resultado:** PASS — nenhuma falha de sintaxe encontrada.

### Parser SSW

Arquivo real utilizado na verificação:

`CSVssw0146RVI[1]230259.sswweb`

Resultado do parser existente:

| Métrica | Resultado |
|---|---:|
| Período detectado | 01/08/2026 a 30/08/2026 |
| Linhas válidas | 2.838 |
| CT-es únicos | 2.566 |
| Linhas com retenção | 157 |
| CT-es únicos com retenção | 152 |

A regra `código 34` / `MERCADORIA EM CONFERENCIA NO CLIENTE` está implementada no parser.

---

# 3. P1 — DIVERGÊNCIAS CRÍTICAS

## P1-01 — Configurações não são uma funcionalidade real

**Mockup:** tela administrativa completa, com salvar alterações, permissões, sincronização, score, alertas, aparência e histórico.  
**Sistema atual:** `config/urls.py` usa `TemplateView` diretamente e `templates/settings/index.html` contém somente inputs estáticos sem `<form>` funcional.

Problemas:

- não persiste valores;
- refresh perde qualquer mudança;
- não existe botão real `Salvar alterações`;
- não gera `AuditLog`;
- não valida pesos = 100%;
- não aplica configurações ao restante do sistema.

**Além disso, `/configuracoes/` não está protegido por `login_required`.**

**Status:** FAIL / P1.

---

## P1-02 — Perfis e permissões não estão implementados

A documentação exige Administrador, Coordenador e Analista.

O app `users` não possui modelo/perfil de negócio. As telas usam apenas autenticação padrão do Django e `login_required`.

Consequências:

- não existe autorização por função;
- analista poderia acessar operações que futuramente deveriam ser restritas;
- a sidebar mostra “Coordenador” para qualquer usuário;
- configurações não possuem proteção específica.

**Status:** FAIL / P1.

---

## P1-03 — Header global exibe estado falso

`templates/components/header.html` mostra sempre:

- `SSW sincronizado`;
- `Última atualização: agora`;
- botão `Atualizar agora`.

Nenhum desses itens está ligado ao estado real da importação.

O botão não possui ação.

**Status:** FAIL / P1.

---

## P1-04 — Sidebar não informa a tela ativa

O mockup exige destaque azul do menu atual.

Todos os links atuais usam somente `class="nav-item"`; não há regra baseada em `request.resolver_match` ou equivalente.

**Status:** FAIL / P1 visual global.

---

## P1-05 — Dashboard está funcional apenas em parte

Itens reais existentes:

- frete total;
- frete retido;
- % retido;
- peso total;
- quantidade de comprovantes;
- taxa geral de entrega.

Itens ausentes/incompletos:

- seletor de período;
- comparação com período anterior;
- situação dos comprovantes;
- ranking com score/peso/retenção/execução;
- ações prioritárias reais;
- navegação dos cards;
- filtros Hoje/Semana/Mês/Ano/Personalizado.

**Status:** FAIL / P1.

---

## P1-06 — Gráfico de evolução do Dashboard usa dados fictícios

Em `static/js/app.js`, as séries de Entregas, Retenções e Pendências estão escritas manualmente:

`[20,35,42,38,50,61,72]`, etc.

O gráfico parece funcional, mas não consulta os dados do banco.

Isso viola a regra de não usar dados hardcoded como solução final.

**Status:** FAIL / P1.

---

## P1-07 — Top Motoristas possui erro de fonte do status de entrega

`DeliveryMovement.status` recebe `SITUACAO` do relatório (ex.: BAIXADO/PENDENTE/CANCELADO).

Porém `dashboard/views.py` calcula `delivered_count` filtrando:

`movements__status__iexact="ENTREGUE"`

O status `ENTREGUE` vem da ocorrência/estado do CT-e, e não necessariamente de `SITUACAO`.

Resultado provável: a coluna “Entregues” do ranking pode ficar incorreta/zerada mesmo com entregas concluídas.

**Status:** FAIL / P1 de dados.

---

## P1-08 — Operação de Hoje não implementa a lógica do mockup

Hoje a tela mostra basicamente movimentos cuja `movement_date` é hoje.

Problemas:

- “Entregas de hoje” é igual ao número de movimentos;
- clientes do dia = `—`;
- peso previsto = `—`;
- “Retiradas possíveis” usa todos os comprovantes WAITING/AVAILABLE, sem cruzar a rota de hoje;
- cards não exibem placa, contagem de entregas/clientes, peso e progresso;
- `Alertas de Retirada` é placeholder;
- não existe cobertura por bairros;
- não existe match exato por cliente/endereço;
- não existe oportunidade regional por bairro.

**Status:** FAIL / P1.

---

## P1-09 — Tela Motoristas não implementa o ranking executivo

Ausentes:

- filtros de período/cidade/status;
- busca;
- score;
- execução;
- retenções;
- recuperados;
- cidades atendidas;
- romaneios;
- tendência;
- paginação server-side;
- ordenação;
- painel Destaques do Período.

**Status:** FAIL / P1.

---

## P1-10 — Perfil do Motorista ainda é um esqueleto

Existe cabeçalho e histórico básico.

Ausentes:

- todos os KPIs do mockup;
- score executivo;
- evolução mensal;
- ocorrências por tipo;
- clientes mais atendidos;
- situação do comprovante no histórico;
- insights calculados;
- comparação contra período anterior.

**Status:** FAIL / P1.

---

## P1-11 — Central de Comprovantes Retidos não possui o fluxo operacional central

A tabela básica existe, mas faltam:

- filtros;
- busca CTRC/NF;
- críticos > N dias calculados;
- disponíveis hoje;
- recuperados;
- valor total retido;
- dias retido;
- endereço completo;
- peso;
- oportunidade;
- drawer lateral;
- “Há rota hoje para este cliente”;
- ação de recuperação;
- gravação de recovery_driver/recovered_at/confirmed_by;
- auditoria da recuperação.

Essa é uma função central do produto.

**Status:** FAIL / P1.

---

## P1-12 — Clientes não possui análise executiva/regional

Tabela básica existente, porém faltam:

- filtros;
- cidade;
- taxa de retenção;
- tempo médio de retorno;
- última visita;
- gráfico de clientes com maior retenção;
- análise por cidade;
- análise por bairro;
- mapa/regionalização baseada em dados reais.

**Status:** FAIL / P1.

---

## P1-13 — Relatórios possuem botões sem função

`Visualizar`, `PDF` e `Excel` são apenas `<button>` sem ação.

Também faltam:

- geração real XLSX;
- geração real PDF;
- relatórios recentes;
- tracking de exportações;
- agenda de envios;
- métricas da tela.

**Status:** FAIL / P1.

---

## P1-14 — Importações SSW não correspondem ao mockup operacional

A tela atual lista execuções, mas faltam:

- Data inicial / Data final;
- Importar período;
- Reprocessar mês;
- timeline real Solicitação → Robô → Download → Validação → Processamento → Banco;
- botão real Atualizar agora;
- próxima execução;
- progresso em tempo real.

**Status:** FAIL / P1.

---

## P1-15 — Robô SSW ainda é apenas adapter/stub

`apps/ssw/services.py::queue_import()` apenas cria um `ImportRun`.

Ainda não existe integração Playwright que:

- faça login no SSW;
- navegue ao relatório;
- informe período;
- gere;
- baixe;
- devolva arquivo;
- processe o arquivo.

**Status:** P1 funcional, embora seja fase posterior prevista na arquitetura.

---

## P1-16 — Reconciliação mensal não está agendada

`CELERY_BEAT_SCHEDULE` possui somente atualização rápida a cada 3 horas.

Não existe job diário das 23:00 para reprocessar o mês atual.

Não existe agendamento de reconciliação histórica.

**Status:** FAIL / P1.

---

## P1-17 — Histórico do Robô está incompleto

Faltam:

- filtros;
- duração;
- nome do arquivo na tabela;
- ações;
- drawer de detalhes;
- timeline de etapas completa;
- mensagens;
- baixar log;
- KPIs calculados.

**Status:** FAIL / P1.

---

## P1-18 — Score Executivo não foi implementado

A fórmula documentada não aparece em serviço/query/model.

Faltam:

- índice operacional;
- índice de esforço;
- normalização;
- score 0–100;
- amostra mínima;
- pesos configuráveis;
- exclusão correta de cancelados;
- testes da regra “conferência no cliente não penaliza”.

**Status:** FAIL / P1.

---

## P1-19 — Não existem testes automatizados

Não foram encontrados arquivos de teste para:

- importação;
- reimportação;
- retenção;
- score;
- permissões;
- recuperação;
- filtros;
- telas;
- E2E.

A homologação não pode ser considerada concluída sem essa camada.

**Status:** FAIL / P1.

---

# 4. P2 — DIVERGÊNCIAS IMPORTANTES

## P2-01 — Login muito distante do mockup

A tela atual possui a divisão básica em duas colunas, porém:

- usa emoji `🚚` em vez de Lucide;
- não possui ilustração/mapa/logística do mockup;
- não possui lembrar acesso;
- não possui mostrar/esconder senha;
- não possui “Esqueci minha senha”;
- não possui os badges de segurança/integração;
- não carrega explicitamente Inter/Lucide no próprio template de login.

---

## P2-02 — Dependência visual de CDNs externas

`base.html` busca:

- Google Fonts;
- Lucide em unpkg;
- ECharts em jsDelivr.

No modo local/offline isso pode resultar em:

- fallback de fonte;
- ícones ausentes;
- gráficos ausentes.

Avaliar empacotamento local dos assets na próxima rodada.

---

## P2-03 — Tabelas não possuem paginação server-side

As telas limitam resultados por slicing (`[:200]`, `[:50]`) ou exibem querysets diretamente.

Não existem:

- paginator;
- sort;
- search;
- filtro persistido em URL.

---

## P2-04 — Filtros de período inexistentes

A maioria das consultas é global, sem período.

Logo, dashboard/motoristas/clientes podem misturar vários meses futuramente.

---

## P2-05 — Client.first_delivery_at e last_delivery_at não são alimentados

Os campos existem, mas o importador não os atualiza.

Isso impede `Última Visita` e histórico correto por cliente.

---

## P2-06 — CTe.delivered_at não é alimentado

O campo está no banco, porém não é definido pelo importador.

---

## P2-07 — AuditLog existe, mas não é usado

O modelo está criado, porém ações críticas ainda não gravam auditoria.

---

## P2-08 — ImportStep não representa todas as etapas aprovadas

O importador registra basicamente:

- Leitura do arquivo;
- Banco atualizado;
- Erro.

O mockup prevê etapas muito mais detalhadas.

---

## P2-09 — Fluxo de staging não existe

A documentação prevê arquivo → staging → validação → normalização → comparação.

A implementação atual processa diretamente em uma transação.

Não é necessariamente um bloqueador para a V1, mas diverge da arquitetura documentada.

---

## P2-10 — Segurança planejada ainda ausente

Não foram identificados:

- CSP configurada;
- rate limit de login;
- autenticação em duas etapas;
- políticas de senha de negócio;
- proteção de configurações por perfil.

---

## P2-11 — Documentação obrigatória está incompleta

O Prompt Mestre prevê arquivos que não existem ainda:

- `DATABASE.md`
- `SSW_IMPORT.md`
- `SSW_ROBOT.md`
- `SCORE.md`
- `PROOFS.md`
- `PERMISSIONS.md`
- `TESTING.md`
- `CHANGELOG.md`

---

## P2-12 — Status visuais não são específicos o bastante

Por exemplo, em `proofs/index.html`, todos os comprovantes recebem `chip-purple`, independentemente do estado.

O mockup exige amarelo/vermelho/verde/roxo conforme situação.

---

# 5. P3 — POLIMENTO

## P3-01
Adicionar microinterações/hover equivalentes aos mockups.

## P3-02
Melhorar glow, shadows e profundidade dos cards.

## P3-03
Ajustar densidade tipográfica/spacing fino por viewport.

## P3-04
Criar estados skeleton/loading semelhantes ao produto final.

---

# 6. MATRIZ POR TELA

| Tela | Estrutura existe | Dados reais | Funcionalidade | Aderência visual | Status |
|---|---|---|---|---|---|
| Login | Sim | N/A | Parcial | Baixa | FAIL |
| Dashboard | Sim | Parcial | Parcial | Média-baixa | FAIL |
| Operação de Hoje | Sim | Parcial | Baixa | Baixa | FAIL |
| Motoristas | Sim | Parcial | Baixa | Baixa | FAIL |
| Perfil Motorista | Sim | Parcial | Baixa | Baixa | FAIL |
| Comprovantes Retidos | Sim | Parcial | Baixa | Baixa | FAIL |
| Clientes | Sim | Parcial | Baixa | Baixa | FAIL |
| Relatórios | Sim | Não | Muito baixa | Média-baixa | FAIL |
| Importações SSW | Sim | Sim/parcial | Parcial | Baixa | FAIL |
| Histórico Robô | Sim | Sim/parcial | Baixa | Baixa | FAIL |
| Configurações | Sim | Não | Estática | Baixa | FAIL |

**Conclusão:** nenhuma tela deve ser marcada como homologada ainda.

---

# 7. O QUE JÁ ESTÁ BEM ENCAMINHADO

## Banco/modelos centrais

Já existem:

- Driver;
- Vehicle;
- Client;
- ClientAddress;
- CTe;
- Manifest (equivalente ao Romaneio);
- DeliveryMovement;
- DeliveryOccurrence;
- RetainedProof;
- ImportRun;
- ImportStep;
- AuditLog.

A modelagem inicial permite evoluir sem reescrever o projeto inteiro.

## Regra de retenção

O parser implementa a regra aprovada:

- código 34;
- descrição “MERCADORIA EM CONFERENCIA NO CLIENTE”.

`RetainedProof` é persistente e o importador contém explicitamente a regra de não recuperar comprovante automaticamente quando o CT-e depois aparece como entregue.

## PostgreSQL

O projeto está preparado para `DATABASE_MODE=postgres`, embora o modo local atual use SQLite por conveniência.

## Design tokens

A paleta principal, sidebar 244px, Inter como alvo e breakpoints básicos já existem no CSS.

---

# 8. OBSERVAÇÃO SOBRE CNPJ E MATCH DE ROTA

O importador atual reconhece corretamente que **o relatório de entregas analisado não fornece CNPJ do destinatário de forma confiável** e, por isso, não usa `CNPJ PAGADOR` como se fosse o CNPJ do cliente.

Isso é correto do ponto de vista de integridade de dados.

Como consequência, enquanto não houver outra fonte confiável de CNPJ, o match de oportunidade deverá priorizar combinações seguras como:

- cliente normalizado + endereço;
- CEP + endereço;
- endereço normalizado;
- posteriormente CNPJ quando disponível em fonte adequada.

Não inventar CNPJ para atender ao mockup.

---

# 9. ORDEM RECOMENDADA DE CORREÇÃO

## Lote 1 — Fundação visual/global

1. Sidebar ativa.
2. Header real e específico por tela.
3. Inter/Lucide/ECharts confiáveis no modo local.
4. Componentes reutilizáveis de KPI, panel, status, filters e tables.
5. Corrigir login.

## Lote 2 — Dashboard Executivo

1. filtro de período;
2. gráficos com banco real;
3. Situação dos Comprovantes;
4. score/ranking;
5. ações prioritárias reais.

## Lote 3 — Operação de Hoje

1. métricas reais;
2. agrupamento de rotas/romaneios;
3. match exato de comprovantes;
4. alertas;
5. bairro/região.

## Lote 4 — Motoristas

1. score;
2. lista executiva;
3. perfil completo;
4. gráficos;
5. filtros/paginação.

## Lote 5 — Comprovantes

1. KPIs;
2. filtros;
3. dias retido;
4. drawer;
5. recuperação;
6. auditoria;
7. oportunidade de rota.

## Lote 6 — Clientes

1. métricas;
2. ranking;
3. tempo médio;
4. análise por bairro/cidade.

## Lote 7 — Relatórios

PDF/XLSX/Recentes/Agendamentos.

## Lote 8 — SSW

Importação web, timeline e histórico detalhado.

## Lote 9 — Robô

Playwright + agenda completa.

## Lote 10 — Configurações e permissões

Persistência + RBAC + auditoria.

---

# 10. CRITÉRIO PARA PRÓXIMA RODADA

A próxima rodada deverá começar **somente por P0/P1**, com prioridade:

1. layout base;
2. sidebar;
3. header;
4. dashboard executivo.

Depois de corrigir esse primeiro lote:

- executar o sistema no Windows;
- capturar screenshot em 1672 × 941;
- comparar contra `docs/mockups/dashboard.png`;
- atualizar este documento com evidência antes/depois;
- somente então avançar para Operação de Hoje.

---

# 11. TESTES A CRIAR ANTES DA HOMOLOGAÇÃO FINAL

- importação do mesmo arquivo 2x sem duplicidade;
- mudança de status de CT-e existente;
- código 34 cria RetainedProof;
- [REGRA SUPERADA] o teste antigo esperava que ENTREGUE não fechasse a retenção. A regra homologada atual exige que CTRC/estado posterior ENTREGUE encerre a retenção ativa de origem SSW, sem inventar motorista recuperador;
- CANCELADO não afeta score;
- conferência no cliente não penaliza score;
- match por cliente/endereço gera oportunidade;
- recuperação persiste motorista/data/usuário;
- filtros e paginação;
- permissões Admin/Coordenador/Analista;
- persistência de configurações;
- E2E das 11 telas.

---

# 12. RESULTADO DA RODADA

**Decisão:** NÃO HOMOLOGADO — seguir para correção P1.

A V0.1.2 deve ser tratada como **fundação técnica executável**, não como implementação final dos mockups.

O próximo pacote deverá atacar somente o **Lote 1 — Fundação visual/global + Dashboard Executivo**, mantendo todo o restante estável até nova comparação.
