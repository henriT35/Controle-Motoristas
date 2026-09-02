# Permissões

- Administrador: controle completo e configurações.
- Coordenador: operação e recuperação de comprovantes quando associado ao grupo `Coordenador` ou quando `is_staff`.
- Analista: visualização e relatórios; não altera configurações críticas.

As verificações são server-side. A tela `/configuracoes/` exige staff/superuser.


## Caderno de Bugs
- `is_staff` / Administrador: visualizar, registrar e editar bugs.
- Usuário comum/Analista sem staff: sem acesso ao módulo.
- A restrição é aplicada server-side em `/bugs/` e `/bugs/<id>/editar/`.
