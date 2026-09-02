# Painel Motoristas — Levantamento de Bugs e Melhorias

**Data do levantamento:** 01/09/2026  
**Status:** Em investigação / levantamento contínuo  
**Objetivo:** Registrar problemas funcionais, lacunas de produto e melhorias antes de iniciar uma nova rodada de correções.

## BUG-001 — Execução fica presa indefinidamente quando o robô SSW não responde
**Severidade:** CRÍTICO  
**Área:** Importações SSW / Orquestração / Worker / Watchdog

**Sintoma observado**
- A execução fica exibindo `Na fila`, `Robô SSW`, `Aguardando executor do robô SSW` e `Processando`.
- O progresso da última execução continua carregando indefinidamente.
- A fila pode permanecer bloqueada esperando um executor que não respondeu ou desapareceu.

**Comportamento esperado**
- Prazo máximo para o executor aceitar/iniciar a tarefa.
- Se o robô não responder: detectar ausência de heartbeat/processo, encerrar tentativa, marcar erro específico, liberar locks/fila, permitir retry e informar a causa na interface.
- Preservar meses anteriores já concluídos.

**Investigar**
- transições entre QUEUED, DISPATCHED, ROBOT_STARTING e RUNNING;
- timeout para tarefa nunca assumida;
- heartbeat do executor;
- processo órfão;
- dispatcher morto;
- lock abandonado;
- worker inexistente;
- reconciliação automática de execuções órfãs após reinício.

**Possíveis códigos**
`ROBOT_DISPATCH_TIMEOUT`, `WORKER_NOT_AVAILABLE`, `WORKER_HEARTBEAT_LOST`, `ORPHAN_QUEUED_JOB`.

> Não assumir a causa sem reproduzir e consultar os logs.

## BUG-002 — Relatórios podem aparecer vazios ou zerados apesar de existir base
**Severidade:** CRÍTICO  
**Área:** Relatórios / Agregações / Filtros

Investigar filtros de data, campo de data, timezone, joins, distinct, filial, status e agregações. Cada relatório deve possuir teste com banco populado comprovando os números apresentados.

## BUG-003 — Drill-down do Mapa Operacional funciona em Belém, mas falha em outros municípios
**Severidade:** ALTO

Clique em qualquer município deve abrir bairros quando houver geodados ou uma visão municipal detalhada quando não houver malha de bairros. Nunca deve simplesmente não responder.

Investigar geodados, event handler, ID IBGE, nome normalizado, parent_region, fallback municipal, API e erro JavaScript silencioso.

## BUG-004 — Regiões com dados não exibem label/valor no mapa
**Severidade:** ALTO

Casos citados: Tapanã e outras regiões/bairros.

Investigar separadamente:
1. região existe na geometria?
2. nome SSW foi normalizado corretamente?
3. métrica chegou no payload?
4. valor foi associado ao polígono?
5. label foi ocultado por regra visual?
6. área é pequena?
7. colisão de labels?
8. nome oficial difere do nome operacional?

Se há dado real, ele precisa ser acessível por hover/click mesmo quando o label visual for ocultado.

## MELHORIA-001 — Histórico da Operação de Hoje
**Prioridade:** ALTA

Os cards das rotas não devem simplesmente desaparecer no fim do dia.

Nova regra:
`dia operacional aberto → atualização das rotas → fechamento do dia → snapshot/histórico → novo dia operacional`.

Deve ser possível consultar hoje, ontem e qualquer data anterior, preservando por rota:
- motorista;
- romaneio;
- CT-es;
- clientes;
- entregues;
- não entregues;
- retenções;
- ocorrência 13;
- comprovantes;
- peso;
- bairros/municípios;
- situação final da rota.

Esse histórico também deve alimentar a avaliação dos motoristas.

## MELHORIA-002 — Novo motor de avaliação dos motoristas
**Prioridade:** ALTA

Separar **Desempenho** de **Produtividade**.

**Produtividade**
- entregas;
- CT-es;
- rotas;
- clientes;
- peso;
- volumes;
- entregas por dia trabalhado.

**Qualidade**
- taxa de sucesso;
- primeira tentativa;
- entrega limpa;
- reentregas;
- pendências deixadas pela rota.

**Retenções**
- ocorrência 34;
- retenções por 100 entregas;
- retenções ativas;
- retenções resolvidas.

**Horário**
- ocorrência 13 `ENTREGA PREJUDICADA PELO HORARIO`;
- taxa de ocorrência 13;
- reincidência.

**Comprovantes**
- comprovantes retidos;
- idade;
- mais antigo;
- acima do SLA;
- tempo médio/mediano de recuperação;
- comprovantes recuperados pelo motorista.

Usar taxas, não só números absolutos.

## MELHORIA-003 — Pontuação extra por recuperação de comprovantes
**Prioridade:** MÉDIA/ALTA

Se o motorista estiver numa rota próxima de cliente com comprovante retido e conseguir recuperá-lo, isso pode gerar pontuação positiva.

Registrar:
- quem recuperou;
- quando;
- evidência;
- validação.

Não incentivar desvio operacional e não permitir autoaprovação sem controle.

## MELHORIA-004 — Perfil operacional completo do motorista
**Prioridade:** ALTA

Adicionar filtros:
- hoje;
- 7 dias;
- semana;
- mês;
- 30 dias;
- período personalizado.

Adicionar:
- nota;
- produtividade;
- entregas/tentativas;
- sucesso;
- entrega limpa;
- retenções;
- ocorrência 13;
- reentregas;
- comprovantes ativos;
- comprovantes recuperados;
- idade média/mediana;
- comprovante mais antigo;
- histórico de rotas;
- desempenho por município/bairro;
- evolução;
- comparação com equipe.

Toda métrica deve permitir drill-down até CT-es/rotas.

## MELHORIA-005 — Link individual seguro do motorista sem vários logins
**Prioridade:** ALTA

Criar link individual por token seguro, não por CPF/ID previsível.

Exemplo conceitual:
`/p/motorista/<token-seguro>`

Mostrar somente dados do motorista:
- operação atual;
- rotas recentes;
- comprovantes relacionados;
- oportunidades de retirada;
- histórico de recuperações.

Token deve ser aleatório, revogável e regenerável.

## MELHORIA-006 — Fluxo de recuperação com foto
**Prioridade:** ALTA

Fluxo sugerido:
`motorista vê comprovante → recupera → envia foto → sistema registra submissão → coordenador valida → comprovante recuperado → motorista recuperador registrado`.

Status possível:
`AGUARDANDO_RETIRADA → DISPONIVEL → EM_RECUPERACAO → AGUARDANDO_VALIDACAO → RECUPERADO`.

## MELHORIA-007 — Oportunidades de retirada próximas da rota
**Prioridade:** ALTA

Sem GPS na primeira fase:
usar município, bairro, cliente e rota.

Mostrar algo como:
`Você possui 3 comprovantes potencialmente recuperáveis nesta rota.`

Disponível no perfil, link individual, card da rota e Operação de Hoje.

## MELHORIA-008 — Clientes com filtros e visão temporal
**Prioridade:** ALTA

Adicionar:
- data inicial/final;
- hoje;
- semana;
- mês;
- 30/60/90 dias;
- motorista;
- município;
- bairro;
- situação;
- ocorrência.

Perfil do cliente:
- entregas;
- tentativas;
- taxa de sucesso;
- retenções;
- ocorrência 13;
- comprovantes;
- recorrência de problemas;
- motoristas;
- histórico por período.

## MELHORIA-009 — Reformular Central de Relatórios
**Prioridade:** ALTA

Relatórios:
- desempenho dos motoristas;
- comprovantes retidos;
- clientes;
- financeiro (revalidar fontes antes);
- operação diária.

Todos precisam:
- filtro de período;
- exportação;
- totalizadores;
- drill-down;
- testes contra base populada.

## MELHORIA-010 — Dashboard
**Prioridade:** MÉDIA

Reavaliar KPIs, comparação com período anterior, alertas, evolução, pendências, operação diária, motoristas em atenção e comprovantes críticos.

Não fazer redesign antes de corrigir a origem dos dados zerados.

## ITEM REVISADO — Semana no Dashboard
O comportamento foi questionado, mas após revisão foi considerado coerente com o calendário corrente.

**Status:** NÃO REGISTRAR COMO BUG por enquanto.

## PRIORIDADE SUGERIDA

**P0**
1. BUG-001 — robô/fila presa indefinidamente.
2. BUG-002 — relatórios vazios/zerados.

**P1**
3. BUG-003 — municípios sem drill-down.
4. BUG-004 — regiões com dados sem informação visível.
5. MELHORIA-001 — histórico da Operação de Hoje.
6. MELHORIA-002 — novo motor de avaliação.
7. MELHORIA-004 — perfil do motorista.
8. MELHORIA-008 — clientes.
9. MELHORIA-009 — relatórios.

**P2**
10. link individual do motorista.
11. upload/validação de comprovante.
12. oportunidades de retirada.
13. pontuação por recuperação.
14. dashboard.

## PRINCÍPIOS PARA A PRÓXIMA FASE
1. Não corrigir tudo simultaneamente.
2. Reproduzir cada bug antes de alterar código.
3. Criar teste de regressão para cada correção.
4. Distinguir bug de melhoria.
5. Validar o banco, não apenas a interface.
6. Não alterar `robot_ssw` sem evidência.
7. Preservar histórico operacional.
8. Pontuação de motorista deve ser auditável.
9. Acesso por link não pode expor dados de outro motorista.


## MELHORIA-011 — Gráfico do Dashboard com calendário operacional inteligente
**Prioridade:** ALTA  
**Área:** Dashboard / Evolução Operacional / UX

### Regra para domingos

O gráfico não deve tratar automaticamente todo domingo como um dia operacional vazio.

Regra desejada:

```text
Domingo sem qualquer movimentação operacional
→ não exibir no eixo temporal do gráfico.

Domingo com movimentação real
→ exibir normalmente no gráfico.
```

Exemplo:

```text
01/08 sexta     → exibir
02/08 sábado    → exibir
03/08 domingo   → sem operação → ocultar
04/08 segunda   → exibir
...
domingo com 3 entregas → exibir
```

### Objetivo

Evitar quedas artificiais para zero que não representam piora operacional, mas apenas um dia em que normalmente não há expediente.

O gráfico deve representar a **evolução da operação**, não a simples existência de todos os dias do calendário.

### Importante

Não remover domingos dos dados históricos.

A regra é apenas de visualização do eixo.

Se existir qualquer evento relevante no domingo, ele deve permanecer visível.

Considerar inicialmente como atividade operacional:
- tentativa;
- saída para entrega;
- entrega;
- retenção;
- ocorrência operacional;
- outra movimentação que faça o dia possuir dados reais.

A definição exata deve ser centralizada e testada.

---

## MELHORIA-012 — Drill-down de um clique a partir do gráfico do Dashboard
**Prioridade:** ALTA  
**Área:** Dashboard / Operação diária / Relatórios / UX

### Objetivo

Transformar o gráfico de Evolução Operacional em uma ferramenta de investigação.

O usuário deve conseguir clicar em qualquer ponto/data do gráfico e abrir imediatamente o detalhamento daquele dia.

### Exemplo

Período selecionado:

```text
01/08/2026 → 01/09/2026
```

Usuário observa:

```text
04/08
Entregas muito altas
```

Clica no ponto `04/08`.

O sistema deve abrir um detalhamento filtrado automaticamente para:

```text
Data = 04/08/2026
```

Outro exemplo:

```text
18/08
Poucas entregas
Muitas retenções
```

Usuário clica no dia.

O sistema mostra imediatamente a operação daquele dia.

### Informações esperadas no drill-down diário

- motoristas;
- romaneios;
- CT-es;
- tentativas;
- entregas;
- entregas limpas;
- não entregues;
- retenções;
- ocorrência 13;
- outras ocorrências relevantes;
- clientes;
- comprovantes;
- peso;
- volumes;
- municípios;
- bairros.

### Comportamento por série

O ponto clicado pode carregar também qual série originou o clique.

Exemplo:

```text
Clique em "Entregas" de 04/08
→ abre 04/08 com destaque/filtro inicial em entregas.

Clique em "Retenções" de 18/08
→ abre 18/08 com destaque/filtro inicial em retenções.
```

Isso não precisa impedir o usuário de visualizar as outras informações daquele dia.

### Navegação desejada

Fluxo recomendado:

```text
Dashboard
→ clicar em data/ponto
→ Operação do Dia / Detalhamento Diário
→ filtros já preenchidos
```

Evitar obrigar o usuário a:
1. lembrar a data;
2. trocar de tela;
3. abrir filtro;
4. selecionar data;
5. executar consulta.

A interação deve ocorrer em um clique.

### Arquitetura

Preferir navegação por parâmetros explícitos, por exemplo:

```text
/operacao/?date=2026-08-04
```

ou equivalente à arquitetura existente.

Se o clique partir da série de retenções:

```text
/operacao/?date=2026-08-04&focus=retentions
```

Não duplicar lógica do Dashboard.

A tela de destino deve utilizar as mesmas regras operacionais/históricas consolidadas.

### Relação com MELHORIA-001

Essa funcionalidade depende diretamente da preservação do histórico da Operação de Hoje.

Quando os cards do dia forem encerrados, eles não podem desaparecer da base lógica.

Precisamos de uma visão:

**Operação do Dia**

que permita consultar qualquer data histórica.

O gráfico será uma das principais portas de entrada para essa visão.

---

## DECISÃO-001 — O Dashboard deve permitir exploração, não apenas visualização
**Status:** Diretriz de produto

A partir desta etapa, gráficos do Painel Motoristas devem ser considerados componentes interativos sempre que existir um detalhamento natural.

Princípio:

```text
Resumo
→ clique
→ detalhe
```

Exemplos futuros:

- ponto de entregas → entregas daquele dia;
- ponto de retenções → retenções daquele dia;
- motorista no ranking → perfil do motorista naquele período;
- bairro no mapa → operação daquela região;
- cliente → perfil/histórico do cliente.

Evitar gráficos puramente decorativos quando os dados possuem drill-down possível.


## BUG-005 — Botão flutuante “Registrar bug” sobrepõe conteúdo e paginação
**Severidade:** ALTO  
**Área:** Caderno de Bugs / UI global / Comprovantes Retidos

**Sintoma observado**
- O botão vermelho flutuante `Registrar bug` fica sobre outros elementos da interface.
- Em telas com listas longas, especialmente **Comprovantes Retidos**, ele pode cobrir controles de paginação ou conteúdo.
- Em alguns casos impede clicar em `Próxima página` ou visualizar corretamente os últimos itens.

**Comportamento esperado**
- O botão nunca deve bloquear conteúdo, filtros, paginação, botões de ação ou informações.
- Deve respeitar safe-area/rodapé e o layout responsivo.

**Soluções a avaliar**
- mover o botão para área fixa da barra lateral;
- incorporar ação ao cabeçalho;
- usar botão flutuante apenas quando não houver conflito;
- reservar espaço de layout para o FAB;
- recolher/minimizar automaticamente próximo ao rodapé/paginação;
- garantir `z-index` correto sem bloquear componentes funcionais.

**Teste obrigatório**
Validar em:
- Comprovantes Retidos com várias páginas;
- Clientes;
- Relatórios;
- Importações;
- resoluções 1920x1080, 1600x900 e 1366x768.

---

## MELHORIA-013 — Refinar filtros de Comprovantes Retidos
**Prioridade:** ALTA  
**Área:** Comprovantes Retidos / UX / Pesquisa

O filtro atual é útil, mas precisa evoluir para permitir investigação operacional mais rápida.

### Filtros sugeridos

**Período**
- hoje;
- ontem;
- 7 dias;
- semana;
- mês;
- 30 dias;
- período personalizado.

**Status**
- aguardando retirada;
- disponível;
- em recuperação;
- aguardando validação;
- recuperado;
- cancelado.

**Idade da retenção**
- 0–1 dia;
- 2–3 dias;
- 4–7 dias;
- 8–15 dias;
- 16–30 dias;
- 30+ dias.

**Operação**
- motorista da tentativa/retenção;
- motorista que recuperou;
- cliente;
- município;
- bairro;
- romaneio;
- CT-e;
- filial.

**Outros**
- somente ativos;
- somente vencidos/acima do SLA;
- com foto/evidência;
- sem evidência;
- recuperados no período.

### UX desejada
- filtros combináveis;
- chips com filtros ativos;
- botão `Limpar filtros`;
- total de resultados;
- manter filtros ao trocar de página;
- URL/querystring refletindo filtros quando possível;
- paginação nunca coberta por elemento flutuante.

---

## REGRA-002 — Preservar motorista da retenção e motorista do resgate separadamente
**Status:** Regra operacional proposta para homologação  
**Área:** Comprovantes / Motoristas / Avaliação

O sistema deve diferenciar claramente:

### Motorista da retenção
É o motorista associado à tentativa/romaneio em que o comprovante/mercadoria ficou retido.

Essa informação é histórica e deve permanecer ligada àquela tentativa.

### Motorista que resgatou o comprovante
É o motorista que posteriormente conseguiu recuperar fisicamente o comprovante.

Ele pode ser diferente do motorista da retenção.

**Nunca sobrescrever um pelo outro.**

Modelo conceitual:

```text
CT-e
Retenção em 05/08
Motorista da tentativa: Motorista A

Comprovante recuperado em 09/08
Motorista recuperador: Motorista B
```

O histórico deve mostrar ambos.

---

## REGRA-003 — Contagem de dias do comprovante retido
**Status:** Reforço de regra já necessária ao projeto

A idade do comprovante deve ser calculada a partir de uma **data operacional real de retenção** (`retained_at` ou equivalente), nunca da data de importação.

Enquanto ativo:

```text
idade = agora/data operacional atual - data real da retenção
```

Quando recuperado:

```text
tempo de retenção = data de recuperação - data real da retenção
```

Exibir no mínimo:
- dias retido;
- data da retenção;
- motorista da retenção;
- status atual;
- data de recuperação quando houver;
- motorista recuperador quando houver.

Para análises:
- média;
- mediana;
- mais antigo;
- faixas de idade;
- acima do SLA.

---

## MELHORIA-014 — Seleção manual do motorista que recuperou o comprovante
**Prioridade:** ALTA  
**Área:** Comprovantes / Coordenação / Motoristas

### Fluxo proposto

Quando um comprovante for baixado/confirmado como recuperado:

```text
Coordenador/responsável
→ abre comprovante
→ ação "Registrar recuperação"
→ informa data/hora
→ seleciona o motorista que recuperou
→ adiciona foto/evidência se aplicável
→ confirma
```

O motorista recuperador deve ser selecionado explicitamente.

Não inferir automaticamente pelo motorista atual do CT-e.

### Auditoria
Registrar:
- comprovante/CT-e;
- motorista recuperador;
- data/hora da recuperação;
- usuário do sistema que registrou;
- evidência/anexo;
- observação;
- data/hora do lançamento no sistema.

Permitir correção apenas com histórico/auditoria.

---

## MELHORIA-015 — Indicador “Comprovantes Resgatados” no desempenho do motorista
**Prioridade:** ALTA  
**Área:** Desempenho / Relatórios / Perfil do Motorista

Adicionar um indicador independente:

**Comprovantes resgatados**

Exibir:
- total no período;
- clientes diferentes;
- tempo médio dos comprovantes recuperados;
- quantos eram de responsabilidade original do próprio motorista;
- quantos eram de outras rotas/motoristas;
- evolução por período.

Criar ranking/relatório:

**Motoristas que mais resgataram comprovantes**

Exemplo:

```text
1. Motorista A — 18 comprovantes
2. Motorista B — 14 comprovantes
3. Motorista C — 11 comprovantes
```

Esse indicador pode compor futuramente a avaliação de desempenho, mas o sistema NÃO deve usar linguagem de recompensa financeira ou benefício.

A decisão sobre qualquer reconhecimento/recompensa é externa ao sistema.

O Painel deve apenas:
- medir;
- registrar;
- apresentar;
- permitir auditoria.

---

## MELHORIA-016 — Caderno de Bugs / Configurações
**Prioridade:** MÉDIA

Revisar a experiência do Caderno de Bugs e das Configurações.

### Caderno de Bugs
- botão de registro sem sobreposição;
- filtros por status/prioridade/módulo;
- anexar screenshot;
- data/hora;
- usuário;
- versão do sistema;
- página onde ocorreu;
- status:
  - aberto;
  - investigando;
  - corrigido;
  - homologado;
  - descartado;
- vínculo com versão de correção.

### Configurações
Reorganizar opções por seção:
- Sistema;
- SSW;
- Filiais;
- Motoristas;
- Comprovantes;
- Mapa;
- Avaliação;
- Diagnóstico.

Evitar misturar configuração operacional com ferramentas de desenvolvimento.
