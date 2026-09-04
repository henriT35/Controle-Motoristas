# QA Release v0.7.0.1

## Escopo
Hotfix do pareamento WhatsApp e da classificação ao vivo de rotas no dia corrente.

## QA portátil
- Python/sintaxe: **PASS — 180 arquivos**.
- JavaScript `node --check`: **PASS — 2 arquivos**.
- `scripts/qa/portable_qa.py`: **PASS — 6/6**.
- comparação byte a byte `robot_ssw` contra v0.7.0.0: **PASS — 17/17 arquivos idênticos**.
- testes estáticos de templates/rotas: **PASS — 56 nomes, nenhuma referência órfã**.
- performance/fórmula/contrato mock do robô: **PASS**.
- adaptador CDP direto: **PASS em Chromium local** para conexão websocket, `Runtime.evaluate`, locator, bounding box e screenshot de elemento.
- nenhuma alteração de model/migration prevista.

## Casos adicionados
- CT-e com `current_status=SAIDA PARA ENTREGA` entra na Operação de Hoje e sai de Planejamento.
- o mesmo estado consolidado não cria rota em uma data histórica.
- período de Dashboard/Entregas que contém hoje inclui a fotografia operacional ao vivo.

## Homologação Windows obrigatória
1. Executar `VERIFICAR_BUILD.bat`.
2. Clicar **Atualizar agora** e validar os romaneios mostrados pelo usuário como saída 85 em 02/09/2026.
3. Confirmar que esses romaneios saíram de Planejamento e aparecem como Confirmados na Operação de Hoje.
4. WhatsApp → Novo pareamento → Gerar QR Code.
5. Confirmar estado técnico `RAW_CDP`, QR visível no Painel, escaneamento e conexão.
6. Enviar uma mensagem de homologação.

## Limitação
O ambiente de empacotamento não possui Django nem navegador Windows real. `manage.py check`, suíte `django.test`, QR real e envio real ficam pendentes para homologação Windows.
