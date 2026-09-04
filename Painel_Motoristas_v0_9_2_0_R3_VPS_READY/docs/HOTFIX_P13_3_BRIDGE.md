# Hotfix p13.3 — Bridge do Painel

## Causa confirmada
A mensagem `Nenhum robô real foi encontrado na pasta robot_ssw` pertence ao bridge experimental p6/p12 e não ao bridge p13 homologado.

Isso significa que o core p13 podia estar instalado corretamente enquanto o processo Django ainda utilizava `apps/ssw/robot_bridge.py` e `dispatch.py` antigos.

## Correção
O hotfix força a substituição da camada de integração Django pelos arquivos p13 e adiciona `BRIDGE_BUILD = 0.2.2-p13.3`.

Não altera o core Playwright homologado nem credenciais.

## Após aplicar
É obrigatório reiniciar o servidor Django para descarregar módulos Python antigos da memória.

Execute `VERIFICAR_BRIDGE_P13.bat` e confirme:

- `Bridge carregado : 0.2.2-p13.3`
- `Bridge antigo detectado: NAO`
