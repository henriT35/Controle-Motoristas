# Auditoria pré-implementação — v0.5.0.0

## Baseline
- Baseline funcional usada: **v0.4.0.3 — Mapa Premium Final**.
- Versão de trabalho: **v0.5.0.0**.
- Stack encontrada: Django/Python, templates server-rendered, CSS/JS, SQLite local e PostgreSQL como alvo.
- O projeto não possui migrations de aplicação versionadas no pacote; o launcher Windows historicamente executa `makemigrations` quando detecta alteração de modelos e depois `migrate`.

## Componentes auditados
Dashboard, Operação, Motoristas, Comprovantes, Clientes, Relatórios, Importações SSW, dispatcher/watchdog, Caderno de Bugs, Configurações, mapa geográfico e `robot_ssw`.

## Componentes de maior risco
1. Estado de execução SSW e fila.
2. Temporalidade: data operacional x data de importação.
3. Relatórios e KPIs históricos.
4. Semântica ROM x CTRC.
5. Retenção atual x evento histórico de retenção.
6. Identidade de cliente durante importação em lote.
7. Geografia: normalização de região x nome do GeoJSON.

## Estado do robot_ssw
O core homologado foi mantido congelado. O hash agregado dos `.py` de `robot_ssw/robot_ssw` é:

`7b3c9a03d91c7d7e9e1ad4d5f811f1b13bfcea9eb4b74939ad8478e309059999`

Esse hash é igual na v0.4.0.3 e na v0.5.0.0 de trabalho.

## Conclusões da auditoria
- **CONFIRMADO:** uma execução `DISPATCHED` podia permanecer ativa por tempo excessivo quando nenhum executor assumia; a reconciliação também dependia demais de novo despacho em fluxos anteriores.
- **CONFIRMADO:** a Central de Relatórios não preservava explicitamente o período selecionado em todos os caminhos de preview/exportação, favorecendo consultas no período padrão.
- **CONFIRMADO:** aliases como `TAPANA (ICOARACI)` podiam agregar dados numa chave normalizada, mas manter display incompatível com o nome do polígono `TAPANA`.
- **CONFIRMADO:** o botão flutuante global de bugs podia disputar a área inferior da tela com paginação/conteúdo.
- **CONFIRMADO:** telas históricas precisavam reconstruir estados no corte temporal, em vez de usar indiscriminadamente o status atual.
- **CONFIRMADO:** o seletor `30 dias` não possuía semântica própria consolidada e podia cair no mês padrão.
- **NÃO TESTADO em runtime neste ambiente:** Django ORM, migrations, templates renderizados, upload real e navegação browser completa, pois Django não está instalado e o ambiente está offline.

## Decisão de arquitetura
A release v0.5.0.0 corrige primeiro integridade/temporalidade, depois expande UX e funcionalidades. A nota V2 de motorista permanece **SIMULAÇÃO** até homologação dos pesos e da classificação de ocorrências negativas.
