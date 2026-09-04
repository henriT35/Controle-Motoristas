# REGRAS IMUTÁVEIS / GUARDRAILS

Estas regras não devem ser alteradas por conveniência de implementação.

## 1. Core do robô SSW
- `robot_ssw` é congelado.
- Preferir corrigir `apps/ssw`, scheduler, bridge, filas, Docker e UI.
- Qualquer mudança no core exige motivo técnico documentado e nova homologação E2E.

## 2. Temporalidade
- Emissão não é execução.
- Importação não é execução.
- CTRC consolidado não define sozinho a tentativa.
- ROM85 é a evidência mais forte da saída.
- ROM13 encerra a tentativa.
- Não migrar romaneio antigo para data nova só porque o CT-e consolidado mudou.

## 3. Retenção
- ROM34 é origem principal.
- CTRC34 é fallback, não substituto automático.
- Não sobrescrever `original_driver` com `recovery_driver`.
- Estado ambíguo pós-retenção deve permanecer `VERIFICAR` até evidência conclusiva.

## 4. Oportunidades
- Retirada exata pode exigir tratamento/justificativa.
- “Ainda não liberado” = neutro.
- Oportunidade regional/de ouro = voluntária; nunca penalizar por não tentar.
- Crédito de recuperação só depois de validação do coordenador.

## 5. Ranking
- Uma Nota Geral principal.
- Produtividade bruta não pontua qualidade.
- Peso/frete/CT-es/quantidade são estatísticas.
- Não punir o mesmo fato várias vezes.
- Bônus devem ser limitados/configuráveis.

## 6. WhatsApp
- Baileys/Node.js é o caminho oficial atual.
- Não reintroduzir automação de login por browser sem decisão explícita.
- WhatsApp é canal; Portal Web é o produto.

## 7. Segurança / Git
Nunca versionar `.env`, credenciais SSW, sessão Baileys, banco, `local_data`, media real, logs reais, `.venv` ou `node_modules`.

## 8. Transparência de QA
Nunca afirmar “testado no Windows/VPS/SSW real” quando apenas houve inspeção estática no Linux/container.
