# QA Release v0.7.0.0

## Escopo
Temporalidade, Dashboard/Operação, Entregas Gerais, detalhe do CT-e, persistência de navegação, fallback geográfico, câmera mobile do Portal e novo núcleo de pareamento/QR do WhatsApp.

## QA executado no ambiente de empacotamento

- Python AST/sintaxe: **PASS — 179 arquivos**.
- JavaScript `node --check`: **PASS — app.js e geo_map.js**.
- `scripts/qa/portable_qa.py`: **PASS — 6/6**.
- Rotas estáticas de templates: **PASS — 56 nomes conhecidos; nenhuma referência órfã**.
- Fórmula de performance: **PASS**.
- Performance estática/import engine: **PASS**.
- Contrato do adaptador/robô mock: **PASS**.
- `robot_ssw` completo comparado byte a byte contra v0.6.0.6: **PASS — 17/17 arquivos idênticos**.
- Models: não foram alterados nesta rodada; **nenhuma migration nova criada**.

## Casos adicionados ao código de testes Django

- temporalidade canônica de romaneios e múltiplas tentativas;
- reconciliação Dashboard/Operação;
- Entregas Gerais;
- fallback geográfico;
- Portal renderiza controles separados de câmera e arquivo;
- upload vindo de `evidence_camera` é aceito como evidência pendente;
- tela dedicada de pareamento WhatsApp existe e contém o QR;
- Central aponta para a tela dedicada de conexão.

## Limitação do ambiente

Django não está instalado no ambiente de empacotamento. Portanto, **não foram executados** aqui:

- `manage.py check`;
- `makemigrations --check`;
- suíte `django.test`;
- homologação com banco real;
- QR real do WhatsApp no Windows;
- câmera real em Android/iOS.

Esses itens permanecem obrigatórios no Windows de homologação antes de promover a versão.

## Homologação crítica no Windows

1. `VERIFICAR_BUILD.bat`.
2. Operação/Dashboard em datas conhecidas, principalmente 01/09/2026.
3. Portal aberto pelo Quick Tunnel HTTPS em celular real: **Tirar foto**, **Escolher arquivo/PDF**, envio e validação.
4. WhatsApp → **Conectar / QR Code** → **Gerar QR Code**.
5. Confirmar no `whatsapp_bootstrap.jsonl` que o modo é `external_cdp`/`EXTERNAL_CDP` e verificar o campo `webdriver` do `bootstrap_metadata`.
6. Escanear o QR, confirmar estado `CONNECTED` e realizar um envio de homologação.
