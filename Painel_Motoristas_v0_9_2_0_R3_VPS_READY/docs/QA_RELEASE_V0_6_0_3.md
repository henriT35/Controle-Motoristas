# QA Release v0.6.0.3

## QA portátil executado

- Compilação/sintaxe Python: PASS.
- `node --check` nos JS do pacote: PASS.
- Simulação isolada de reconstrução do `browser_profile`: PASS.
- Estado `ERROR` persistível no state store: PASS.
- Comparação `robot_ssw`: 17/17 arquivos idênticos à v0.6.0.2: PASS.
- Models não alterados: sem migration nova.

## Não declarado como testado

O ambiente de empacotamento não possui Django/Playwright Windows real nem uma sessão WhatsApp utilizável. Portanto permanecem pendentes:

- abertura real de Chrome/Edge no Windows;
- detecção visual da mensagem real do WhatsApp Web;
- reconstrução com IndexedDB real bloqueado/corrompido;
- geração/scan de QR real;
- persistência da sessão após pareamento;
- envio real de homologação.

Esses itens devem ser homologados no computador operacional antes de considerar o bug encerrado.
