---
name: fabric-readonly
description: Consulta dados do Microsoft Fabric (Lakehouse/Warehouse da Quero-Quero, ex. Neg_BT) em modo SOMENTE LEITURA pelo SQL analytics endpoint (T-SQL/MSSQL). Use quando o usuário pedir para consultar, explorar, contar, listar tabelas, descrever colunas ou extrair dados do Fabric/Lakehouse/OneLake, ou mencionar tabelas de um Lakehouse do Fabric. Também ensina a pegar a cadeia de conexão SQL no portal do Fabric e configurar o acesso.
---

# Fabric — consulta somente leitura

O SQL analytics endpoint de um Lakehouse no Fabric é um SQL Server (TDS, porta 1433) acessado com login Microsoft (Entra ID). Esta skill conecta nele **apenas para leitura** com o script `scripts/fabric_query.py`.

Caminhos usados abaixo (funciona em macOS, Linux e Windows):
- `PY` = Python do ambiente da skill:
  - macOS/Linux: `~/.config/fabric-readonly/venv/bin/python`
  - Windows: `%USERPROFILE%\.config\fabric-readonly\venv\Scripts\python.exe` (no Git Bash do Claude Code: `~/.config/fabric-readonly/venv/Scripts/python.exe`)
- `Q` = `<pasta desta skill>/scripts/fabric_query.py`

## 1. Primeiro uso: verifique antes de qualquer consulta

Verifique se o `PY` acima existe e rode `$PY $Q profiles`.

- Se o ambiente não existir → rode `python3 <pasta da skill>/scripts/setup.py` (Windows: `py` ou `python` no lugar de `python3`). Faça sem perguntar; só instala dependências locais. Ele imprime o caminho exato do `PY`.
  - Se faltar Python 3.10+: oriente a instalar (macOS `brew install python`; Windows `winget install Python.Python.3.12`; Ubuntu/Debian `sudo apt install python3 python3-venv`).
  - Linux, se a conexão falhar por biblioteca ausente: Debian/Ubuntu `sudo apt install -y libltdl7 libkrb5-3 libgssapi-krb5-2`; RHEL/Fedora `sudo dnf install -y libtool-ltdl krb5-libs`.
- Se não houver perfil → **siga o onboarding do passo 2** antes de responder o pedido original. Ao terminar, volte e atenda o que o usuário pediu.

## 2. Onboarding (pessoa que acabou de instalar)

Conduza a pessoa assim, em tom curto e amigável:

**a) Explique em 2 linhas:** a skill consulta o Fabric só para leitura; ela precisa apenas do **link de conexão SQL** e do **login Microsoft da empresa** no navegador. Não existe senha de banco.

**b) Abra o guia com prints** e mostre o passo a passo no chat:

```bash
$PY $Q guia      # abre guia/index.html no navegador e imprime os passos
```

Passos para mostrar no chat (as imagens estão em `guia/`):
1. Em app.fabric.microsoft.com, em **Acesso rápido → Workspaces recentes**, clicar no workspace (ex.: `Neg_BT`). Print: `guia/passo1-workspace.webp`.
2. Na lista de itens, abrir o item do tipo **Lakehouse** (casinha azul). O nome dele é o **nome do banco**. Print: `guia/passo2-lakehouse.webp`.
3. Clicar na **engrenagem (Configurações)** na barra do Lakehouse. Print: `guia/passo3-configuracoes.webp`.
4. No menu lateral, clicar em **Ponto de extremidade de análise de SQL** e usar o **botão de copiar** ao lado de "Cadeia de conexão SQL". O texto na tela vem cortado com `...`, então **use o botão**. O link termina em `.datawarehouse.fabric.microsoft.com`. Print: `guia/passo4-copiar-link.webp`.

**c) Peça o link e o nome do Lakehouse.** Se o link colado não terminar em `.fabric.microsoft.com`, peça para copiar de novo pelo botão.

**d) Salve, faça o login e teste:**

```bash
$PY $Q setup --profile <nome_minusculo> --server "<link>" --database <NomeLakehouse> --default
$PY $Q login     # rodar em background: abre o navegador; avise a pessoa para entrar com a conta da empresa
$PY $Q test
```

Avise antes do `login`: "vai abrir uma aba do navegador com o login da Microsoft; entre com sua conta da empresa". Rode-o em background e espere terminar. Se a aba não abrir (SSH, WSL, Linux sem interface gráfica), use `login --device-code`; em Linux sem `DISPLAY` isso já acontece sozinho. Nesse modo, leia a saída do comando em background e mostre à pessoa a URL (`https://microsoft.com/devicelogin`) e o código impressos, para ela entrar por qualquer navegador, até no celular.

**e) Confirme o sucesso** mostrando com qual usuário conectou e rodando `tables` para listar o que a pessoa enxerga.

Pré-requisito de acesso: a conta precisa de permissão de leitura no workspace/item (função Viewer, ou o item compartilhado com "Read all data using SQL"). Erro 18456 / "not authorized" = falta permissão; oriente a pessoa a pedir acesso ao dono do workspace.
Se a conta tiver vários tenants, adicione `--tenant <tenant-id>` no `setup`.

Quem preferir configurar pelo terminal, sem o Claude, pode rodar `$PY $Q init`: um assistente interativo que mostra o guia, pergunta o link e o nome, faz o login e testa.

## 3. Consultar

```bash
$PY $Q tables [--like vendas]                     # schemas/tabelas/views
$PY $Q describe dbo.minha_tabela                       # colunas e tipos
$PY $Q query "SELECT TOP 20 * FROM dbo.[2024_vendas]"
$PY $Q query --file consulta.sql --format csv --out resultado.csv --max-rows 0
```

Opções: `--profile <nome>`, `--max-rows N` (padrão 200; `0` = tudo), `--format table|csv|json`, `--out arquivo`.

### Boas práticas ao consultar
- Comece por `tables` e `describe` antes de escrever SQL; não chute nomes de coluna.
- Dialeto é **T-SQL**: `TOP n` (não `LIMIT`), colchetes para nomes que começam com número ou têm caracteres especiais (`[2024_vendas]`), schema padrão `dbo`.
- Tabelas podem ser grandes: prefira agregações (`COUNT`, `GROUP BY`) e filtros de data; use `TOP` para amostras.
- Para extrações grandes, salve em arquivo com `--out` em vez de imprimir no terminal.
- Dados de clientes (CPF, conta, nome) são sensíveis: não reproduza listas inteiras na conversa sem necessidade; mostre amostras/agregados.

## 4. Garantias de somente leitura

O script bloqueia antes de enviar ao servidor qualquer coisa que não seja **uma única** instrução `SELECT`/`WITH`, e recusa palavras como `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `EXEC`, `INTO`, `SET`, `DECLARE`, `COPY` etc. Além disso conecta com `ApplicationIntent=ReadOnly`, `autocommit=False` e sempre faz `ROLLBACK` no final. O próprio endpoint de Lakehouse já é somente leitura para as tabelas Delta.

**Nunca** contorne isso (não use outro cliente, `sqlcmd`, ou execute SQL de escrita por outro caminho). Se o usuário pedir alteração de dados, explique que esta skill é só leitura.

## 5. Problemas comuns

| Sintoma | Causa / ação |
|---|---|
| `Perfil ... não configurado` | Rodar `setup` (passo 2). |
| Login abre de novo toda vez | Rodar `login` uma vez; ele salva `~/.config/fabric-readonly/auth_record.json`. |
| `Login failed` / 18456 / not authorized | Conta sem acesso ao workspace/item, ou tenant errado (`--tenant`). |
| Timeout / host não encontrado | Cadeia copiada incompleta (o campo da tela vem truncado) ou VPN/firewall bloqueando a porta 1433. |
| `Invalid object name` | Ver nome exato com `tables`; usar `[colchetes]` e `dbo.` |
| Tabela recém-criada não aparece | O endpoint SQL sincroniza metadados com atraso de alguns minutos. |
