# QA Release v0.8.0.0

## Resultado disponível no ambiente de empacotamento

- Sintaxe Python: **PASS — 183 arquivos**.
- JavaScript: `static/js/app.js`, `static/js/geo_map.js` e `whatsapp_bridge/server.mjs`: **PASS**.
- QA portátil: **6/6 PASS**.
- Fórmula de performance: **PASS**.
- Contrato `robot_ssw`: **PASS**.
- Rotas/templates estáticos: **PASS — 60 nomes conhecidos**.
- QA Baileys: **PASS**.
- QA instalador Node Windows: **PASS**.
- QA contrato de telefone brasileiro com/sem 9: **PASS**.
- QA estático VPS/Docker: **PASS**.
- `robot_ssw`: **17/17 arquivos idênticos à v0.7.1.1**.
- Models/migrations: **nenhuma alteração de schema nesta release**.

## O que NÃO foi marcado como homologado

O ambiente de empacotamento não possui Django/Docker instalados. Portanto ainda exigem prova real na Hostinger:

1. `docker compose build`/subida completa;
2. PostgreSQL e `migrate --run-syncdb` sobre banco de homologação;
3. login Django via IP público;
4. Celery Beat/Redis e frequência configurável;
5. worker SSW Linux → login → opção 036 → download → importação;
6. QR real do Baileys no container e envio real;
7. reboot da VPS e retorno automático de todos os serviços.

Nenhum item acima deve ser chamado de PASS antes do teste real.
