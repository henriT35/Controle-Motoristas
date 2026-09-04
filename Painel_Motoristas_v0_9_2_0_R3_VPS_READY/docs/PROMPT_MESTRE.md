# PROMPT MESTRE — IMPLEMENTAÇÃO COMPLETA DO PAINEL DE MOTORISTAS

Quero que você desenvolva um sistema web completo chamado provisoriamente **Painel Motoristas**, utilizando como referência visual obrigatória todas as telas/mockups anexados.

IMPORTANTE:

As imagens NÃO são apenas inspiração.

Elas representam o produto que queremos construir.

O objetivo é reproduzir com alta fidelidade:

- layout;
- hierarquia;
- navegação;
- cores;
- tipografia;
- cards;
- tabelas;
- filtros;
- gráficos;
- indicadores;
- alertas;
- comportamento;
- funcionalidades;
- interações.

Porém, NÃO quero apenas uma cópia estática das imagens.

Cada elemento existente nas imagens deverá possuir uma função real, alimentada pelo banco PostgreSQL e pelas informações importadas do SSW.

---

# 1. OBJETIVO DO SISTEMA

Construir uma plataforma web executiva para acompanhamento da operação de entregas e desempenho dos motoristas.

O sistema deverá transformar relatórios do SSW em:

- histórico permanente;
- indicadores executivos;
- indicadores operacionais;
- acompanhamento individual de motoristas;
- acompanhamento de clientes;
- controle de comprovantes retidos;
- identificação de oportunidades de retirada;
- acompanhamento diário de rotas;
- análise por cidade;
- análise por bairro;
- relatórios;
- automação da coleta de dados através de robô SSW.

O sistema deverá possuir duas características simultaneamente:

### Executivo

Permitir que coordenadores entendam rapidamente a operação.

### Operacional

Permitir identificar pendências e tomar ações durante as rotas.

---

# 2. STACK OBRIGATÓRIA

## Backend

Python.

Preferencialmente:

**Django 5+**

Utilizar:

- Django ORM;
- Django Templates;
- Django Authentication;
- Django Forms quando aplicável;
- Django Admin para administração técnica;
- CSRF;
- migrations.

Não criar uma SPA React desnecessariamente.

A interface principal poderá ser server-rendered com:

- Django Templates;
- HTMX;
- Alpine.js;
- JavaScript moderno.

---

# 3. BANCO DE DADOS

Banco obrigatório:

**PostgreSQL**

Utilizar tipos adequados.

Valores monetários:

`DecimalField`

Nunca utilizar float para valores financeiros.

Peso:

Decimal.

Datas e horários:

timezone-aware.

Timezone padrão da aplicação:

**America/Belem**

Armazenar datas internamente de maneira consistente e apresentar em:

`dd/mm/yyyy`

Moeda:

**BRL / R$**

Locale:

**pt-BR**

---

# 4. COMPONENTES DE INFRAESTRUTURA

Arquitetura sugerida:

- Django
- PostgreSQL
- Redis
- Celery
- Celery Beat
- Playwright para automação SSW
- Gunicorn
- Nginx ou Caddy
- Docker / Docker Compose

Celery deverá executar:

- sincronizações SSW;
- processamento de arquivos;
- geração de relatórios;
- tarefas periódicas;
- reconciliações.

---

# 5. PRINCÍPIO DA ARQUITETURA

Separar claramente:

## SISTEMA

É o cérebro.

Responsável por:

- escolher períodos;
- solicitar atualizações;
- comparar dados;
- identificar alterações;
- deduplicar;
- armazenar histórico;
- gerar indicadores;
- gerar alertas;
- gerar relatórios.

## ROBÔ SSW

É apenas executor.

Recebe do sistema algo semelhante a:

```python
buscar_relatorio(
    data_inicio="01/08/2026",
    data_fim="30/08/2026",
    tipo="entregas"
)

```

O robô deverá:

1. abrir o SSW;
2. autenticar;
3. navegar até o relatório;
4. preencher período;
5. gerar relatório;
6. aguardar geração;
7. baixar arquivo;
8. retornar arquivo para o sistema;
9. registrar resultado.

Nenhuma regra de negócio importante deve existir somente dentro do robô.

---

# 6. ESTRATÉGIA DE SINCRONIZAÇÃO

Implementar três níveis.

## ATUALIZAÇÃO RÁPIDA

Default:

**a cada 3 horas**

Janela:

últimos 15 dias.

Objetivo:

capturar alterações recentes.

---

## RECONCILIAÇÃO DO MÊS

Executar diariamente.

Default:

**23:00**

Buscar:

primeiro dia do mês até hoje.

---

## HISTÓRICO

Permitir ao administrador solicitar:

01/01/2026 → 31/12/2026

O sistema deverá quebrar automaticamente o período.

Exemplo:

01/01 → 31/01

01/02 → 28/02

01/03 → 31/03

etc.

Nunca depender de uma consulta anual gigante no SSW.

---

# 7. IMPORTAÇÃO IDEMPOTENTE

Regra obrigatória:

**Importar novamente não pode duplicar informações.**

Fluxo:

arquivo recebido

→ staging

→ validação

→ normalização

→ comparação

→ insert / update / ignore

Registrar em cada execução:

- novos;
- atualizados;
- sem alteração;
- ignorados;
- erros.

---

# 8. ESTRUTURA DE APPS DJANGO

Sugestão:

```text
apps/
    core/
    users/
    drivers/
    clients/
    operations/
    ssw/
    proofs/
    dashboard/
    reports/
    notifications/
    audit/

```

---

# 9. MODELOS PRINCIPAIS

## Driver

Campos mínimos:

- id
- nome
- cpf
- ativo
- data\_criacao
- data\_atualizacao

---

## Vehicle

- placa
- descrição
- ativo

---

## Client

- id
- razão/nome
- cnpj
- ativo
- data\_primeira\_entrega
- data\_ultima\_entrega

Não duplicar cliente somente porque apareceu novamente no relatório.

---

## ClientAddress

- cliente
- endereço
- bairro
- CEP
- cidade
- UF
- endereço\_normalizado
- latitude futura
- longitude futura

Um cliente poderá possuir vários endereços.

---

## CTe

Representa o documento de transporte.

Campos:

- código CTRC
- NF
- remetente
- cliente
- valor\_frete
- valor\_mercadoria
- peso
- volumes
- situação atual
- datas relevantes

O CT-e deve ser único através de uma chave de negócio estável.

Não tratar cada repetição no relatório como um novo CT-e.

---

## Romaneio

- número
- data
- motorista
- veículo
- situação

---

## DeliveryMovement

Representa cada passagem/tentativa de um CT-e em uma rota.

Campos:

- CT-e
- romaneio
- motorista
- veículo
- cliente
- endereço
- data
- status
- ocorrência
- tentativa
- peso
- volumes

---

## DeliveryOccurrence

Guardar histórico.

Campos:

- CT-e
- movimento
- código ocorrência
- descrição
- data
- hora
- origem
- data\_importacao

Nunca apagar a ocorrência anterior simplesmente porque surgiu outra.

---

# 10. REGRA DE COMPROVANTE RETIDO

Regra oficial inicial:

Ocorrência SSW:

**código 34**

ou descrição contendo:

**MERCADORIA EM CONFERENCIA NO CLIENTE**

significa:

**COMPROVANTE RETIDO**

Ao detectar a ocorrência:

criar ou atualizar registro no banco de comprovantes.

IMPORTANTE:

Um CT-e poderá depois aparecer como:

**ENTREGUE**

Isso significa entrega da mercadoria.

NÃO significa automaticamente que o comprovante voltou.

Portanto:

**ENTREGA DA MERCADORIA != RECUPERAÇÃO DO COMPROVANTE**

---

# 11. MODELO RetainedProof

Campos:

- id
- CT-e
- NF
- cliente
- endereço
- motorista\_original
- romaneio\_original
- data\_retenção
- valor\_frete
- valor\_mercadoria
- peso
- volumes
- status
- data\_recuperação
- motorista\_recuperação
- usuário\_que\_confirmou
- observação

Status:

```text
AGUARDANDO_RETIRADA
DISPONIVEL_HOJE
EM_RECUPERACAO
RECUPERADO
CANCELADO

```

---

# 12. RECUPERAÇÃO

Ao recuperar:

registrar:

- data;
- hora;
- motorista;
- usuário;
- observação.

Não apagar a retenção.

Preservar para histórico.

---

# 13. CRUZAMENTO DE ROTAS

Ao carregar a operação diária:

comparar cada parada com os comprovantes abertos.

Prioridade do match:

1. CNPJ exato;
2. CNPJ + endereço;
3. CEP;
4. endereço normalizado;
5. cliente + endereço.

Quando houver correspondência:

gerar:

**RETIRADA DISPONÍVEL HOJE**

Exemplo:

```text
Centrofarma
3 comprovantes pendentes
Há entrega neste cliente hoje
Motorista: João
Romaneio: BEL045001

```

---

# 14. BAIRROS

O relatório SSW já possui bairro.

Criar indicadores por bairro desde a V1.

Não exigir geocodificação para isso.

Mostrar:

- entregas por bairro;
- peso por bairro;
- clientes por bairro;
- retenções por bairro;
- comprovantes pendentes por bairro.

A funcionalidade:

“motorista está passando perto”

será uma evolução futura.

Inicialmente poderemos sinalizar:

**Existe pendência no mesmo bairro da rota.**

Esse alerta deverá ser marcado como:

**OPORTUNIDADE POR REGIÃO**

e não como match exato.

---

# 15. GEOLOCALIZAÇÃO — FASE FUTURA

Preparar ClientAddress para:

- latitude;
- longitude.

Futuramente utilizar:

- geocoding;
- distância;
- raio;
- mapas;
- proximidade da rota.

Não bloquear a V1 por causa disso.

---

# 16. REGRAS DE DESEMPENHO

Nunca avaliar motorista somente pela quantidade de CT-es.

Separar:

## VOLUME

- CT-es;
- entregas;
- volumes;
- peso;
- frete;
- valor da mercadoria.

## ESFORÇO

- romaneios;
- paradas;
- clientes;
- cidades;
- bairros;
- peso.

## EXECUÇÃO

- entregas concluídas;
- pendentes;
- tentativas;
- ocorrências.

## DOCUMENTAÇÃO

- retenções;
- comprovantes recuperados;
- comprovantes pendentes.

---

# 17. REGRA IMPORTANTE SOBRE RETENÇÕES

“Conferência no cliente” NÃO deverá diminuir automaticamente o score do motorista.

Pode ser regra operacional do cliente.

O sistema deverá mostrar retenção como indicador, mas não como culpa automática do motorista.

---

# 18. SCORE EXECUTIVO INICIAL

Criar fórmula configurável.

Versão inicial:

## Índice Operacional

```text
(entregas_normais + entregas_com_conferencia_cliente)
/
movimentações

```

## Índice de Esforço

Normalizado entre os motoristas do período:

```text
35% movimentações
25% paradas
20% romaneios
20% peso

```

## Score Executivo

```text
60% índice operacional
40% índice de esforço

```

Exibir:

0 a 100.

Pesos deverão ser editáveis em Configurações.

Motoristas com amostra muito pequena deverão aparecer como:

**AMOSTRA BAIXA**

e não competir no ranking principal.

Default:

mínimo 20 movimentações.

---

# 19. DESIGN SYSTEM

As screenshots anexadas são a referência visual principal.

Não redesenhar o sistema em outro estilo.

## Estilo

- dark mode executivo;
- premium;
- logística / centro de controle;
- moderno;
- denso, porém organizado;
- leitura rápida;
- sem aparência de template Bootstrap genérico.

---

# 20. REFERÊNCIA DE RESOLUÇÃO

Os mockups foram produzidos aproximadamente em:

**1672 x 941**

proporção:

**16:9**

Desenvolver desktop-first.

Referência mínima confortável:

1440px.

Não travar a interface em tamanho fixo.

---

# 21. RESPONSIVIDADE

## >= 1440px

Layout completo.

Sidebar fixa.

Múltiplas colunas.

## 1024–1439px

Reduzir gaps.

Alguns cards quebram linha.

Painéis laterais podem ir para baixo.

## Tablet

Sidebar recolhível.

Tabelas com scroll horizontal controlado.

## Mobile

Não tentar comprimir o dashboard inteiro.

Utilizar:

- drawer;
- cards verticais;
- filtros em modal/drawer;
- tabelas adaptadas;
- KPIs empilhados.

---

# 22. SIDEBAR

Desktop:

largura aproximada:

**240–250px**

Fundo:

```css
#07111F

```

Item ativo:

fundo azul escuro / gradiente.

Altura aproximada de item:

48–52px.

Ícones:

20–22px.

---

# 23. CONTEÚDO

Padding principal:

24px.

Gap:

16px.

Cards:

border-radius:

12–16px.

Borda:

1px.

---

# 24. PALETA

Criar CSS Variables.

```css
--bg-main: #07111F;
--bg-sidebar: #081321;
--surface-1: #0D1A2B;
--surface-2: #101F33;
--surface-hover: #142842;

--border: #1D3552;

--text-primary: #F8FAFC;
--text-secondary: #CBD5E1;
--text-muted: #94A3B8;

--primary: #2563EB;
--primary-bright: #1D73FF;

--cyan: #06B6D4;
--green: #22C55E;
--yellow: #F59E0B;
--red: #EF4444;
--purple: #8B5CF6;

```

Não utilizar cores aleatórias em telas diferentes.

---

# 25. TIPOGRAFIA

Utilizar:

**Inter**

Fallback:

```css
font-family:
Inter,
ui-sans-serif,
system-ui,
-apple-system,
BlinkMacSystemFont,
"Segoe UI",
sans-serif;

```

Pesos:

400 normal

500 labels

600 títulos

700 KPIs

Tamanhos aproximados:

Page title:

28–32px.

Card KPI:

30–36px.

Section title:

18–20px.

Body:

14px.

Label:

12–13px.

---

# 26. ÍCONES

Utilizar preferencialmente:

**Lucide Icons**

Manter:

- mesmo stroke;
- mesmo tamanho;
- aparência consistente.

Não utilizar emojis como ícones de interface.

Exemplos:

- LayoutDashboard
- CalendarDays
- Users
- ClipboardList
- Building2
- ChartNoAxesCombined
- CloudDownload
- Settings
- Truck
- Weight
- DollarSign
- TriangleAlert
- CheckCircle
- MapPin
- RefreshCw
- Download
- FileSpreadsheet
- FileText
- Bot
- Database
- Clock
- Route

---

# 27. GRÁFICOS

Utilizar preferencialmente:

**Apache ECharts**

ou equivalente profissional.

Configuração dark personalizada.

Não usar gráficos com aparência default.

Características:

- background transparente;
- grid line com baixa opacidade;
- tooltip escuro;
- legendas compactas;
- animações suaves;
- line width 2–3px;
- markers 4–6px;
- sem excesso de elementos.

---

# 28. TABELAS

Tabelas deverão possuir:

- paginação server-side;
- ordenação;
- filtros;
- busca;
- estados vazios;
- loading;
- erro;
- hover;
- linha selecionada;
- exportação quando aplicável.

Altura aproximada:

Header:

44px.

Row:

50–56px.

Não carregar milhares de registros de uma vez no navegador.

---

# 29. TELA 1 — LOGIN

Reproduzir o mockup.

Layout dividido.

Esquerda:

- branding;
- ilustração logística;
- prévia do dashboard.

Direita:

card de autenticação.

Campos:

- usuário;
- senha.

Funcionalidades:

- login real;
- lembrar acesso;
- mostrar/esconder senha;
- recuperação futura;
- mensagens de erro;
- bloqueio após tentativas excessivas;
- CSRF.

---

# 30. TELA 2 — DASHBOARD EXECUTIVO

Tela inicial do coordenador.

KPIs:

- Frete Total Movimentado;
- Frete Retido;
- % Frete Retido;
- Peso Total;
- Comprovantes Retidos;
- Taxa Geral de Entrega.

Filtros:

- hoje;
- semana;
- mês;
- ano;
- personalizado.

Mostrar variação vs período anterior.

Gráficos:

## Evolução Operacional

Séries:

- entregas;
- retenções;
- pendências.

## Valor Retido x Liberado

Donut.

## Situação dos Comprovantes

- aguardando retirada;
- recuperados;
- críticos;
- disponíveis hoje.

## Ranking Top Motoristas

Colunas:

- rank;
- motorista;
- score;
- entregas;
- peso;
- retidos;
- execução.

## Ações Prioritárias

Exemplos:

- comprovantes antigos;
- rotas com retirada;
- clientes com muitas retenções.

Todos os cards devem abrir a visão detalhada relacionada.

---

# 31. TELA 3 — OPERAÇÃO DE HOJE

Mostrar:

- motoristas em rota;
- entregas de hoje;
- clientes do dia;
- peso previsto;
- retiradas possíveis.

Cada card de rota:

- motorista;
- placa;
- romaneio;
- entregas;
- clientes;
- peso;
- bairros;
- cidades;
- oportunidades de retirada.

Clique:

abrir rota.

Painel:

**Alertas de Retirada**

Mostrar:

- cliente;
- endereço;
- quantidade pendente;
- ação.

## Cobertura por bairros

Mostrar:

- bairro;
- quantidade;
- percentual;
- entregas;
- retenções.

O mapa esquemático poderá existir caso exista base cartográfica adequada.

Não inventar mapas incorretos.

---

# 32. TELA 4 — MOTORISTAS

Filtros:

- período;
- cidade;
- status;
- busca.

KPIs:

- motoristas ativos;
- score médio;
- peso movimentado;
- valor retido.

Tabela:

- motorista;
- CPF;
- cidades;
- entregas;
- romaneios;
- peso;
- valor retido;
- recuperado;
- execução;
- score;
- tendência.

Painel:

**Destaques do período**

- maior volume;
- maior score;
- maior valor retido.

Clique no motorista:

abrir perfil.

---

# 33. TELA 5 — PERFIL DO MOTORISTA

Header:

- nome;
- CPF;
- status;
- cidades atendidas.

KPIs:

- movimentações;
- CT-es;
- peso;
- valor movimentado;
- comprovantes retidos;
- recuperados;
- score executivo.

Gráficos:

## Evolução mensal

## Ocorrências por tipo

## Clientes mais atendidos

Tabela:

**Histórico de atividades**

- data;
- romaneio;
- cliente;
- cidade;
- peso;
- ocorrência;
- comprovante.

Criar insights calculados.

Exemplo:

“Melhorou 4,2% vs mês anterior.”

Não utilizar IA generativa para afirmações que podem ser calculadas diretamente.

---

# 34. TELA 6 — COMPROVANTES RETIDOS

Título:

**Central de Comprovantes Retidos**

Filtros:

- cliente;
- motorista;
- cidade;
- bairro;
- dias retido;
- situação;
- CTRC;
- NF.

KPIs:

- aguardando retirada;
- críticos;
- disponíveis hoje;
- recuperados;
- valor retido.

Tabela:

- CTRC;
- NF;
- cliente;
- endereço;
- bairro;
- motorista original;
- data retenção;
- dias retido;
- frete;
- peso;
- situação;
- oportunidade.

Cores:

amarelo:

aguardando.

vermelho:

crítico.

verde:

recuperado.

roxo:

retirada disponível.

Ao clicar:

abrir drawer lateral.

Mostrar:

- CT-e;
- NF;
- cliente;
- endereço;
- pendências do cliente;
- valor;
- peso;
- oportunidade.

Se houver rota:

**HÁ ROTA HOJE PARA ESTE CLIENTE**

Botão:

**Ver rota**

---

# 35. CRITÉRIO DE CRÍTICO

Configuração inicial:

mais de:

**15 dias**

de retenção.

Deve ser configurável.

---

# 36. TELA 7 — CLIENTES

KPIs:

- clientes atendidos;
- clientes com retenção;
- taxa média de retenção;
- valor retido.

Tabela:

- cliente;
- CNPJ;
- cidade;
- entregas;
- retenções;
- taxa;
- valor;
- tempo médio retorno;
- última visita.

Painel:

**Clientes com maior retenção**

Bar chart.

## Análise regional

Inicial:

por cidade e bairro.

No futuro:

mapa geográfico real.

Importante:

identificar clientes que naturalmente retêm muitos comprovantes.

Isso ajuda a não atribuir a retenção injustamente ao motorista.

---

# 37. TELA 8 — RELATÓRIOS

Criar:

**Central de Relatórios**

Categorias:

- Desempenho dos Motoristas;
- Comprovantes Retidos;
- Clientes;
- Operação Diária;
- Importações SSW;
- Financeiro.

Ações:

- Visualizar;
- PDF;
- Excel.

Filtros por período.

## Relatórios Recentes

Tabela:

- nome;
- tipo;
- período;
- formato;
- criado em;
- usuário;
- status.

## Agendamento

Permitir posteriormente:

- diário;
- semanal;
- mensal.

Não enviar e-mail sem configuração explícita.

---

# 38. EXPORTAÇÃO EXCEL

Gerar XLSX real.

Não simplesmente CSV renomeado.

Aplicar:

- títulos;
- filtros;
- formatos;
- moeda;
- peso;
- datas;
- cabeçalho.

---

# 39. EXPORTAÇÃO PDF

Gerar relatório executivo.

Não fazer screenshot HTML.

Criar template de relatório apropriado.

---

# 40. TELA 9 — IMPORTAÇÕES SSW

KPIs/configurações:

### Atualização rápida

Automática.

Exemplo:

3 horas.

### Reconciliação mensal

Diária às 23h.

### Importação histórica

Sob demanda.

## Executar Importação

Campos:

- data inicial;
- data final.

Ações:

- Importar período;
- Reprocessar mês.

## Timeline

Etapas:

Solicitação

→ Robô SSW

→ Download

→ Validação

→ Processamento

→ Banco atualizado.

Mostrar estado real de Celery/robô.

---

# 41. IMPORTAÇÕES RECENTES

Tabela:

- início;
- fim;
- tipo;
- período;
- novos;
- atualizados;
- sem alteração;
- status.

---

# 42. TELA 10 — HISTÓRICO DO ROBÔ

KPIs:

- execuções;
- taxa sucesso;
- tempo médio;
- erros;
- reprocessamentos.

Tabela:

- data/hora;
- período;
- tipo;
- arquivo;
- novos;
- atualizados;
- sem alteração;
- duração;
- status.

Drawer lateral:

**Detalhes da execução**

Mostrar etapas, timestamps e mensagens.

Permitir:

**Baixar log**

Nunca incluir senha do SSW no log.

---

# 43. TELA 11 — CONFIGURAÇÕES

Somente perfis autorizados.

Seções:

## Geral

- período padrão;
- timezone;
- moeda;
- casas decimais.

## Sincronização SSW

- frequência;
- reconciliação;
- histórico;
- retenção logs.

## Alertas

- dias críticos;
- limites;
- e-mails.

## Pontuação e Indicadores

Editar pesos.

Validar:

total dos pesos = 100%.

## Usuários e Permissões

- perfis;
- acesso;
- política senha.

## Aparência

- tema;
- accent;
- densidade.

## Histórico de alterações

Registrar todas as mudanças administrativas.

---

# 44. PERFIS

Inicialmente:

## Administrador

Tudo.

## Coordenador

Dashboard, operação, motoristas, clientes, comprovantes, relatórios.

Pode recuperar comprovantes.

## Analista

Visualização e exportação.

Configurações críticas não permitidas.

---

# 45. AUDITORIA

Registrar:

- usuário;
- ação;
- registro;
- valor anterior;
- valor novo;
- timestamp;
- IP quando útil.

Principalmente:

- recuperação comprovante;
- alteração configuração;
- importações;
- alteração score;
- usuários.

---

# 46. SEGURANÇA

Obrigatório:

- .env;
- nunca versionar senha;
- senha SSW criptografada / secrets;
- CSRF;
- CSP;
- validação uploads;
- limitação de login;
- logs sanitizados;
- permissões server-side.

Nunca confiar apenas em ocultar botão no HTML.

---

# 47. PERFORMANCE

Criar índices PostgreSQL principalmente para:

- CTRC;
- CPF;
- CNPJ;
- data;
- motorista;
- cliente;
- bairro;
- cidade;
- status comprovante;
- romaneio.

Utilizar:

`select_related`

e:

`prefetch_related`

onde necessário.

Indicadores grandes poderão utilizar:

- query agregada;
- materialized view futuramente;
- cache Redis.

---

# 48. TESTES

Criar testes obrigatórios.

## Importação

Importar mesmo arquivo duas vezes:

resultado:

0 duplicados.

## Atualização

CT-e existente com novo status:

atualiza.

## Retenção

Ocorrência 34:

cria comprovante.

## Entregue após retenção

Usar ROM x CTRC: ROM=34 preserva histórico; CTRC=34 mantém retenção ativa; CTRC posterior `1 / ENTREGUE` baixa automaticamente o comprovante na data/hora do CTRC. Recuperação manual confirmada tem precedência.

## Cancelado

não prejudica motorista.

## Match rota

mesmo CNPJ/endereço:

gera oportunidade.

## Score

conferência cliente não penaliza.

## Permissão

analista não altera configuração.

---

# 49. TESTES E2E

Playwright.

Cobrir:

login;

dashboard;

filtros;

motorista;

retidos;

recuperação;

importação;

configuração.

---

# 50. DADOS DE HOMOLOGAÇÃO

Utilizar dados fictícios ou dados do relatório fornecido apenas em ambiente controlado.

Não gerar alterações no SSW real durante desenvolvimento sem autorização.

Criar:

`DEMO_MODE`

quando possível.

---

# 51. ESTADOS DE INTERFACE

Toda tela deve possuir:

- loading;
- vazio;
- erro;
- sucesso;
- sem resultado;
- permissão negada.

Não deixar tela branca se API/query falhar.

---

# 52. FILTROS

Filtros devem refletir na URL sempre que possível.

Exemplo:

```text
/motoristas/?periodo=2026-08&cidade=BELEM

```

Isso permite:

- voltar;
- compartilhar;
- salvar visão.

---

# 53. NAVEGAÇÃO

URLs sugeridas:

```text
/login/

/dashboard/

/operacao/hoje/

/motoristas/
/motoristas/<id>/

/comprovantes/
/clientes/

/relatorios/

/ssw/importacoes/
/ssw/historico/

/configuracoes/

```

---

# 54. DIRETRIZ VISUAL MAIS IMPORTANTE

NÃO transformar os mockups em uma interface genérica.

Manter:

- sensação premium;
- dark executive;
- excelente espaçamento;
- números grandes;
- status visual;
- tabelas elegantes;
- interação rápida.

A interface deverá parecer um:

**CENTRO DE CONTROLE OPERACIONAL LOGÍSTICO**

e não um CRUD Django comum.

---

# 55. PRIORIDADE DE IMPLEMENTAÇÃO

Não tente construir tudo simultaneamente.

Executar por fases.

## FASE 1 — Fundação

Criar:

- projeto;
- PostgreSQL;
- autenticação;
- design system;
- layout;
- sidebar;
- permissões.

## FASE 2 — Dados

Criar:

- modelos;
- staging;
- importador manual SSW;
- deduplicação;
- histórico.

## FASE 3 — Dashboard

Implementar dashboard real com dados.

## FASE 4 — Motoristas

Lista + perfil.

## FASE 5 — Comprovantes

Banco de retenções.

## FASE 6 — Operação diária

Rotas + alertas.

## FASE 7 — Clientes

Indicadores.

## FASE 8 — Relatórios

PDF/XLSX.

## FASE 9 — Robô

Playwright + Celery.

## FASE 10 — Configurações

Administração.

---

# 56. REGRA DE DESENVOLVIMENTO

Para cada fase:

1. implementar;
2. executar migrations;
3. rodar testes;
4. validar interface;
5. comparar com mockup;
6. corrigir;
7. documentar;
8. somente então avançar.

---

# 57. NÃO FAZER

Não:

- usar dados hardcoded como solução final;
- criar gráfico fictício no ambiente real;
- duplicar CT-es;
- misturar mercadoria entregue com comprovante recuperado;
- penalizar retenção automaticamente;
- remover histórico;
- armazenar senha em código;
- substituir o design por template genérico;
- ignorar responsividade;
- criar funções sem testes.

---

# 58. DOCUMENTAÇÃO DO CÓDIGO

Criar:

```text
/docs/
    README.md
    ARCHITECTURE.md
    DATABASE.md
    SSW_IMPORT.md
    SSW_ROBOT.md
    BUSINESS_RULES.md
    SCORE.md
    PROOFS.md
    DESIGN_SYSTEM.md
    PERMISSIONS.md
    TESTING.md
    CHANGELOG.md

```

Toda decisão nova deverá ser registrada.

---

# 59. PRIMEIRO PASSO A EXECUTAR

Antes de começar a criar páginas aleatoriamente:

1. analisar todos os mockups anexados;
2. criar inventário de componentes;
3. criar design tokens;
4. criar arquitetura Django;
5. criar modelo de dados;
6. criar migrations;
7. criar layout base;
8. criar sidebar;
9. implementar a Dashboard como primeira tela real.

A Dashboard deve utilizar dados reais do banco.

Depois dela, seguir as fases estabelecidas.

---

# 60. ENTREGA ESPERADA

Quero um sistema funcional, não um protótipo.

Ao final deverá ser possível:

SSW

→ relatório

→ robô/importação

→ PostgreSQL

→ atualização

→ processamento

→ indicadores

→ dashboard

→ acompanhamento do motorista

→ detecção de comprovante retido

→ banco de pendências

→ nova rota

→ alerta de retirada

→ recuperação

→ histórico

→ relatório executivo.

Esse é o fluxo central do produto.

A interface final deverá reproduzir fielmente as telas anexadas, mas todos os números, cards, tabelas, gráficos, alertas e ações deverão ser alimentados por regras e dados reais do sistema.