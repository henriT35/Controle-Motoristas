# Relatório final de engenharia — v0.5.0.0

**Baseline de origem:** v0.4.0.3 — Mapa Premium Final  
**Nova versão:** v0.5.0.0  
**Situação:** baseline completa **candidata à homologação de runtime**.

## 1. Objetivo da rodada
A v0.5.0.0 consolida a investigação dos bugs levantados e implementa a primeira rodada de evolução operacional do Painel Motoristas. O trabalho foi feito preservando o core homologado do robô SSW e priorizando integridade temporal, rastreabilidade e drill-down antes de novos elementos visuais.

## 2. Bugs tratados

| ID | Resultado | Causa principal |
|---|---|---|
| BUG-001 — execução SSW eterna | Corrigido no código; runtime pendente | `DISPATCHED` sem executor/heartbeat podia permanecer sem fechamento e a reconciliação não era acionada com frequência suficiente |
| BUG-002 — relatórios zerados/vazios | Corrigido parcialmente; runtime/DB pendente | período não era propagado de forma uniforme para preview/PDF/XLSX |
| BUG-003 — mapa só aprofunda Belém | Fallback implementado | municípios sem malha de bairros não tinham caminho de detalhe útil |
| BUG-004 — Tapanã/dado sem polígono | Corrigido | nome bruto e chave canônica podiam divergir (`TAPANA (ICOARACI)` x `TAPANA`) |
| BUG-005 — botão Registrar bug cobre paginação | Corrigido no layout; browser pendente | FAB fixo ocupava área de interação inferior |
| BUG-006 — período 30 dias | Corrigido | ausência de caminho rolling explícito consolidado |
| BUG-007 — filtro sem evidência | Corrigido | query não representava corretamente o complemento dos comprovantes com evidência |
| BUG-008 — KPI histórico com estado atual | Corrigido | consultas antigas podiam ler estado presente em vez do estado no corte |
| BUG-009 — maior taxa de retenção por valor | Corrigido | seleção usava valor financeiro e exibia taxa |

Detalhes e evidências: `docs/BUGS_CAUSA_RAIZ.md`.

## 3. Melhorias implementadas

### Orquestração SSW
- timeout de despacho separado do timeout de execução/importação;
- detecção de heartbeat perdido e PID desaparecido;
- reconciliação de execuções órfãs também pelo polling da interface;
- códigos de erro explícitos e fila liberada/pausada em falha.

### Operação do Dia e Dashboard
- consulta histórica por data;
- fechamento temporal sem deixar entregas futuras contaminarem dias anteriores;
- domingo sem movimento omitido somente do gráfico;
- domingo com operação preservado;
- clique nas séries do gráfico abre o detalhe do dia e pode carregar foco em entregas/retenções/comprovantes.

### Comprovantes
- motorista da retenção separado do motorista recuperador;
- idade baseada na data operacional real;
- registro manual de recuperação com motorista explícito e auditoria;
- submissão com evidência e validação;
- filtros por período, idade, status, motorista, região, SLA e evidência;
- recuperação direta de comprovante cancelado bloqueada sem fluxo auditável.

### Motoristas
- perfil analítico V2;
- produtividade separada de desempenho;
- retenção da tentativa baseada em ROM34 e comprovante ativo como indicador separado;
- recuperação de comprovantes como indicador mensurável;
- confiança de amostra;
- nota V2 em **modo SIMULAÇÃO**, com explicação da composição.

### Portal do motorista
- acesso simplificado por token aleatório, revogável e regenerável;
- escopo restrito ao motorista;
- oportunidades de retirada por contexto de rota/região;
- envio de evidência para validação do coordenador.

### Clientes / Relatórios / Mapa / Bugs
- filtros temporais e perfil analítico de cliente;
- Central de Relatórios com período preservado e datasets ampliados;
- mapa com alias geográfico e fallback municipal;
- Caderno de Bugs com causa raiz, resolução/reteste e versão;
- Configurações reorganizadas por domínio.

## 4. Regras de domínio preservadas
- data de importação nunca substitui data operacional;
- ROM34 = evento histórico daquela tentativa;
- CTRC34 = estado consolidado observado como retido;
- CTRC posterior `ENTREGUE` pode encerrar a retenção ativa originada no SSW;
- esse fechamento automático não identifica motorista recuperador;
- motorista da retenção e motorista recuperador são fatos diferentes;
- ocorrência 13 continua significando `ENTREGA PREJUDICADA PELO HORARIO`;
- a nota V2 não é oficial nesta release: permanece em simulação.

## 5. Core robot_ssw
Os 6 arquivos homologados do core foram comparados com a v0.4.0.3 e permaneceram idênticos.

Hash agregado determinístico do core (concatenação dos bytes em ordem lexicográfica):

`7b3c9a03d91c7d7e9e1ad4d5f811f1b13bfcea9eb4b74939ad8478e309059999`

Manifest individual: `robot_ssw/HOMOLOGATED_CORE.sha256`.

## 6. QA executado neste ambiente
- sintaxe Python: **163/163 PASS**;
- QA portátil: **6/6 PASS**;
- análise estática de performance: **PASS**;
- fórmula Avaliação V2: **PASS** (`93,2` cenário limpo, `50,0` cenário crítico);
- contrato mockado da opção 036: **PASS**;
- rotas estáticas em templates: **33 nomes / 0 órfãs — PASS**;
- JavaScript: **2/2 PASS no `node --check`**;
- core robot_ssw: **6/6 hashes PASS**;
- distribuição limpa de banco/log/.env/credencial local/cache Python: **PASS**.

## 7. QA não executado
Por ausência de Django e de ambiente operacional real neste empacotamento, ficaram **NÃO TESTADOS**:
- `manage.py check`;
- geração e aplicação de migrations;
- suíte `django.test`;
- upgrade de cópia do banco real;
- renderização e fluxos em browser real;
- upload HTTP real;
- execução contra SSW real.

Esses itens não devem ser considerados PASS por inferência.

## 8. Migrations
Não foi criada migration manual nesta etapa porque o projeto herdado não versiona migrations de aplicação no pacote e o ambiente atual não possui Django. Como há alterações de models, a v0.5.0.0 **exige homologação de schema antes de produção**.

Procedimento obrigatório:
1. backup do banco;
2. usar cópia/banco de homologação;
3. iniciar a nova baseline com a `.venv` real;
4. gerar/aplicar migrations conforme o launcher;
5. executar `VERIFICAR_BUILD.bat`;
6. revisar o schema gerado;
7. executar testes Django;
8. somente depois promover.

## 9. Limitações conhecidas / itens adiados
- múltiplas filiais ainda não possuem proveniência histórica suficiente no movimento para misturar BEL/CWB/etc. na mesma base com separação histórica garantida;
- geodados de bairros não existem para todos os municípios; nesses casos a v0.5.0.0 usa fallback municipal;
- relatório financeiro continua limitado aos fatos financeiros realmente persistidos;
- avaliação V2 está em simulação até homologação dos pesos/regras;
- integração automática com grupo de mensagens não faz parte desta fase;
- GPS/rastreamento do motorista não faz parte desta fase.

## 10. Status final
**Código e pacote:** prontos como baseline candidata.  
**QA portátil:** PASS.  
**Homologação Django/banco/browser/SSW real:** PENDENTE.

A versão não deve substituir a produção diretamente sem passar pelo roteiro de homologação descrito em `docs/QA_RELEASE.md` e `VERIFICAR_BUILD.bat`.
