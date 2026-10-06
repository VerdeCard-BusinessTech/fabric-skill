# fabric-readonly

Skill do Claude Code para consultar o Microsoft Fabric (Lakehouse/Warehouse) **somente leitura**, via SQL analytics endpoint.

## O que você precisa
- Mac com Python 3.10+ (`python3 --version`).
- Acesso de leitura ao workspace no Fabric (sua conta da empresa).
- O **link de conexão SQL** do Lakehouse. Veja o guia com prints em [`guia/index.html`](guia/index.html).
- **Não precisa de senha de banco.** O login é feito no navegador com sua conta Microsoft.

## Instalação rápida: só mandar para o Claude

No **Claude Code** (app desktop, aba Code, ou terminal), cole esta mensagem:

> Instale a skill https://github.com/VerdeCard-BusinessTech/fabric-skill clonando em ~/.claude/skills/fabric-readonly e depois me ajude a configurar o acesso ao Fabric.

O Claude clona, instala o ambiente, mostra o guia para pegar o link, abre o login da Microsoft no navegador e testa. Você só cola o link e faz o login.

## Instalação manual
1. Clone o repositório direto na pasta de skills do Claude:
   ```bash
   git clone https://github.com/VerdeCard-BusinessTech/fabric-skill.git ~/.claude/skills/fabric-readonly
   ```
   Para atualizar depois: `git -C ~/.claude/skills/fabric-readonly pull`.
2. Abra o Claude Code e peça qualquer consulta, por exemplo: *"liste as tabelas do Fabric"*.
   Na primeira vez o Claude instala o ambiente, mostra o guia para pegar o link, pede o link, abre o login da Microsoft no navegador e testa a conexão.

Prefere configurar pelo terminal, sem o Claude?
```bash
bash ~/.claude/skills/fabric-readonly/scripts/setup.sh
~/.config/fabric-readonly/venv/bin/python ~/.claude/skills/fabric-readonly/scripts/fabric_query.py init
```

## O que fica salvo no seu Mac
- `~/.config/fabric-readonly/venv`: ambiente Python (`mssql-python` e `azure-identity`).
- `~/.config/fabric-readonly/config.json`: link e nome do banco de cada perfil.
- `~/.config/fabric-readonly/auth_record.json`: identifica a conta logada (não contém senha nem token).
- Token de acesso: guardado no Keychain do macOS.

Para desfazer tudo: `rm -rf ~/.config/fabric-readonly ~/.claude/skills/fabric-readonly`.

## Segurança
Só consultas `SELECT`/`WITH`, uma por vez. Comandos de escrita são bloqueados antes de chegar ao servidor. A conexão também é aberta em modo leitura e desfeita com rollback no final. Cada pessoa só enxerga o que a própria conta tem permissão para ver no Fabric.
