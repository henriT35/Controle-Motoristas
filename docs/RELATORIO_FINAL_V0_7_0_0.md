# Relatório Final — Painel Motoristas v0.7.0.0

## Base
v0.6.0.6

## Resultado da rodada
A versão concentra uma correção estrutural de temporalidade e amplia a camada operacional. Durante a homologação surgiram dois bugs adicionais bloqueadores, incorporados antes do fechamento da baseline: câmera do Portal e pareamento WhatsApp.

## Portal — causa da câmera
O Portal usava um único `<input type="file">` com `accept="image/*,application/pdf"` e `capture="environment"`. Em navegadores móveis essa combinação pode fazer o modo de captura ser ignorado porque o mesmo seletor representa simultaneamente câmera e documentos.

### Correção
- `evidence_camera`: apenas `image/*` + `capture="environment"`;
- `evidence_file`: imagem/PDF sem `capture`;
- backend aceita as duas origens e mantém compatibilidade com `evidence` legado;
- submissão continua pendente de validação.

## WhatsApp — evidência da falha anterior
O diagnóstico da v0.6.0.6 mostrou que o comando de permissão `persistent-storage` retornava sucesso, mas o navegador continuava reportando permissão `prompt` e `storagePersisted=false`; o WhatsApp seguia entrando em `post_logout`/erro de storage. Por isso o core anterior foi abandonado como estratégia principal.

### Novo núcleo de pareamento
- Chrome/Edge/Chromium é iniciado como processo normal, fora do launcher Playwright;
- usa `user-data-dir` exclusivo;
- CDP é aberto apenas em `127.0.0.1` numa porta dinâmica;
- Playwright conecta depois via `connect_over_cdp` apenas para captura/controle;
- o QR visível tem prioridade sobre `post_logout` e mensagens de storage;
- nova tela dedicada **Conectar WhatsApp** exibe o QR diretamente;
- profile só vira sessão ativa após conexão confirmada;
- encerramento do bot também encerra o navegador externo.

## Segurança
A porta CDP não escuta interfaces externas. O navegador usa profile isolado do Chrome pessoal do usuário. O bot continua sem leitura/monitoramento de conversas.

## Banco / migrations
Nenhuma alteração de model nesta rodada. Nenhuma migration nova.

## Robô SSW
`robot_ssw` preservado: 17/17 arquivos idênticos à v0.6.0.6 no comparador byte a byte.

## Pendente de homologação
QR real, envio real e câmera real precisam ser provados no Windows/celular do ambiente operacional.
