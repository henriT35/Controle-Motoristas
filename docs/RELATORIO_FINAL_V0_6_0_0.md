# Relatório final de engenharia — v0.6.0.0

**Base:** v0.5.0.1  
**Nova versão:** v0.6.0.0  
**Escopo:** Operação temporal, avaliação de motoristas, comprovantes, portal mobile, WhatsApp Bot V1, geografia dinâmica, clientes e relatórios.

## Implementado

### Operação
- `DATA EMISSAO ROMANEIO` não é tratada como prova do dia da rota.
- Saída 85 classifica rota como Confirmada.
- Outra ocorrência ROMANEIO datada pode classificar histórico como Inferido.
- Romaneio sem fato operacional fica em Planejamento/Data não confirmada.

### Motoristas
- Qualidade, Produtividade e Confiança estão separadas.
- Ranking usa shrinkage da qualidade para a média da equipe conforme tamanho da amostra.
- Volume aumenta confiança/produtividade; não vira qualidade automaticamente.
- Recuperação validada tem bônus pequeno e limitado.

### Comprovantes e portal
- Portal mostra operação, planejamento e oportunidades.
- Upload mobile aceita câmera/galeria/PDF.
- Upload cria evidência PENDING; não baixa comprovante automaticamente.
- Coordenador valida, rejeita ou solicita nova foto vendo contexto completo.
- Locks transacionais evitam dupla validação/recuperação concorrente.

### WhatsApp
- Central administrativa com prontidão de cadastro e histórico.
- Envio em lote por data, individual por motorista e por romaneio.
- Sessão do WhatsApp Web persistida localmente.
- Bot não lê/respond conversas e é opcional para o funcionamento do Painel.

### Mapa
- Bairro é resolvido por UF + município + bairro normalizado.
- Alias de Tapanã permanece.
- Dominância municipal pode entrar em nível bairro mesmo sem provider estático quando há bairros reais na operação.
- Resolvedor dinâmico usa cache e fallback textual para não descartar dados não resolvidos.

## Banco/migrations

O pacote herdado não versiona migrations geradas da instalação. Como existem alterações de models, o primeiro startup em homologação deve gerar/aplicar migrations automaticamente pelo launcher. Faça backup antes.

## QA executado no empacotamento

- Sintaxe de todos os Python.
- QA portátil e invariantes do importador.
- Fórmula da avaliação V2.
- Contrato mockado do robot SSW.
- Referências estáticas de rotas/templates.
- `node --check` em todos os JS de `static/`.
- Comparação do `robot_ssw` com a v0.5.0.1 após limpeza de caches.
- Integridade do ZIP e simulação de aplicação do patch.

## QA ainda obrigatório na instalação real

O ambiente de empacotamento não possui Django instalado. Portanto a homologação Windows deve executar `VERIFICAR_BUILD.bat`, migrations e testes funcionais no navegador/banco real.

## Limitações conhecidas

- WhatsApp Web pode exigir reconexão/QR; a V1 não promete sessão eterna.
- Polígonos de bairros não estão disponíveis de forma confiável para todos os municípios; nesses casos o sistema mantém fallback textual e diagnóstico.
- Avaliação V2 continua sendo ferramenta operacional/simulação até homologação dos pesos pela gestão.
