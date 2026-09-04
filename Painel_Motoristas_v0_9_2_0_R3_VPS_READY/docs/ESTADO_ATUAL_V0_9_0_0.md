# ESTADO ATUAL DA v0.9.0.0 — NÃO CONFUNDIR COM RELEASE HOMOLOGADA

A grande v0.9.0.0 foi especificada integralmente, porém a release funcional/homologada ainda não deve ser considerada concluída apenas com base na documentação.

**Baseline funcional segura para retomar:** v0.8.2.0.

**Versão-alvo:** v0.9.0.0.

O prompt completo está em `docs/PROMPT_IMPLEMENTACAO_V0_9_0_0.txt`.

O próximo agente deve primeiro inspecionar a árvore real da baseline e implementar/validar cada item. Não assumir que uma descrição no CHANGELOG significa que o código correspondente já foi homologado.

### Pontos que já existiam na v0.8.2.0
- temporalidade e retenções corrigidas na rodada v0.8.1.0;
- Entregas Gerais/CT-e detalhado;
- Portal básico por token com envio de comprovante;
- Baileys/Node.js;
- envio WhatsApp em lote e edição de telefone;
- Docker/VPS base;
- rotinas SSW e scheduler Windows;
- gráfico ampliável/zoom da v0.8.2.0;
- responsividade parcial.

### Pontos da v0.9 ainda exigindo implementação/fechamento
- ranking unificado V3 completo e calibrável;
- solicitação de novo link no Portal;
- ressalva de retenção e estados de tentativa de retirada;
- oportunidades de ouro com impacto/projeção;
- ranking mobile e painel administrativo Top 3;
- Central WhatsApp totalmente unificada;
- tela QR em card único;
- modal das rotinas corrigido em resoluções pequenas;
- performance severa/cache/lazy loading medido;
- mapa com validação de bairro/município e retry;
- política formal de migrations para produção;
- QA final e empacotamento de release.
