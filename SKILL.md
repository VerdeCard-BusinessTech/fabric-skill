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

## 0. Instalação: detecte o sistema antes de tudo

O público inclui pessoas não técnicas (back office). Fale em linguagem simples, um passo por vez, sem jargão. Antes de cada comando que vai pedir permissão, diga em uma frase o que ele faz.

**a) Confirme que está no computador da pessoa.** Se você estiver num sandbox na nuvem, por exemplo no chat do claude.ai (diretórios como `/home/claude` ou `/mnt/user-data`, sem acesso ao `~/.claude` real da pessoa), **não instale**. Explique de forma simples:
1. "Eu estou no chat do site, que não consegue instalar nada no seu computador. Precisamos usar o app Claude na aba **Code**."
2. Baixar o app em **claude.ai/download** (Windows ou Mac) e entrar com a mesma conta.
3. Clicar na aba **Code**, não na de chat. Se pedir uma pasta, escolher qualquer uma, como *Documentos*.
4. Colar lá a mesma mensagem de instalação e clicar em **Permitir** quando o Claude pedir para rodar comandos.
5. No Linux não existe app: instalar pelo terminal com `curl -fsSL https://claude.ai/install.sh | bash` e rodar `claude`.

**b) Detecte o sistema operacional** antes de escolher comandos:
- `uname -s 2>/dev/null || echo Windows`: `Darwin` = macOS, `Linux` = Linux, `MINGW*`/`MSYS*`/`CYGWIN*` ou erro = Windows (Git Bash ou PowerShell).
- macOS: confira a versão com `sw_vers -productVersion`. O driver exige **macOS 15+**. Se for mais antigo, avise que não vai funcionar e pare.
- Linux: confira a distro com `cat /etc/os-release`.

**c) Instale conforme o sistema** (a pasta da skill é `~/.claude/skills/fabric-readonly`; no Windows, `%USERPROFILE%\.claude\skills\fabric-readonly`):

| Sistema | Python (se faltar 3.10+) | Git (se faltar) | Setup |
|---|---|---|---|
| macOS | instalador de python.org/downloads (mais simples para leigos) ou `brew install python` | `xcode-select --install` | `python3 <skill>/scripts/setup.py` |
| Windows | `winget install Python.Python.3.12` (depois reabra o terminal/app) | `winget install Git.Git` | `py <skill>\scripts\setup.py` (ou `python`) |
| Debian/Ubuntu | `sudo apt install -y python3 python3-venv` | `sudo apt install -y git` | `python3 <skill>/scripts/setup.py` + `sudo apt install -y libltdl7 libkrb5-3 libgssapi-krb5-2` |
| RHEL/Fedora | `sudo dnf install -y python3` | `sudo dnf install -y git` | `python3 <skill>/scripts/setup.py` + `sudo dnf install -y libtool-ltdl krb5-libs` |

Comandos com `sudo` pedem a senha do computador: avise a pessoa antes. O `setup.py` imprime o caminho exato do `PY`; use esse caminho dali em diante.

Depois do setup, siga para o onboarding (passo 2).

## 1. Primeiro uso: verifique antes de qualquer consulta

Verifique se o `PY` acima existe e rode `$PY $Q profiles`.

- Se o ambiente não existir → faça a instalação do passo 0 (sem perguntar; ela só instala dependências locais).
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

**f) Apresente o guia rápido no chat.** Rode `$PY $Q ajuda` e **mostre a saída na conversa**, no próprio chat, sem só dizer que existe. Ela já vem em Markdown com:
- a configuração da pessoa;
- exemplos do que pedir;
- a tabela de padrões (tempo máximo de 5 min por consulta, 200 linhas no chat, 20 consultas simultâneas no batch, cache de 24h, somente leitura);
- a explicação do batch e o que fazer em caso de erro.

Mantenha o conteúdo e a tabela de padrões **como vieram**, porque os números saem do código e estão sempre certos. Pode encurtar a introdução. Termine com: *"Quer fazer a primeira consulta? Me diga o que precisa e o período."*

**Guia rápido a qualquer momento:** quando a pessoa perguntar *"o que essa skill faz?"*, *"como funciona?"*, *"quais são os padrões/limites?"*, *"ajuda do Fabric"* ou pedir o guia rápido, rode `$PY $Q ajuda` e apresente a saída da mesma forma.

**Mudando padrões a pedido:** traduza o pedido em opções do comando, só para aquela consulta:

| Pedido | Opção |
|---|---|
| "pode demorar mais" | `--timeout <seg>` |
| "traga tudo" | `--max-rows 0` (e prefira `--out arquivo.csv`) |
| "atualize a lista de tabelas" | `--refresh` |
| "use o Lakehouse Y" | `--profile y` |

Nunca mude o modo somente leitura.

Pré-requisito de acesso: a conta precisa de permissão de leitura no workspace/item (função Viewer, ou o item compartilhado com "Read all data using SQL"). Erro 18456 / "not authorized" = falta permissão; oriente a pessoa a pedir acesso ao dono do workspace.
Se a conta tiver vários tenants, adicione `--tenant <tenant-id>` no `setup`.

Quem preferir configurar pelo terminal, sem o Claude, pode rodar `$PY $Q init`: um assistente interativo que mostra o guia, pergunta o link e o nome, faz o login e testa.

## 3. Consultar

```bash
$PY $Q tables [--like vendas]                          # tabelas/views (cache local, 0 janelas)
$PY $Q describe dbo.tab_a dbo.tab_b                    # colunas de várias tabelas (cache local, 0 janelas)
$PY $Q query "SELECT TOP 20 * FROM dbo.[2024_vendas]"  # 1 consulta = 1 janela
$PY $Q batch a.sql b.sql c.sql [--out-dir pasta/]      # N consultas em paralelo = mesma janela
$PY $Q batch --json consultas.json                     # {"nome": "SELECT ...", ...}
```

Opções: `--profile <nome>`, `--max-rows N` (padrão 200; `0` = tudo), `--format table|csv|json`, `--out arquivo`, `--timeout S` (padrão 300s; `0` = sem limite), `--refresh` (em `tables`/`describe`: recarrega a estrutura do Fabric), `--workers N` (batch; padrão 20).

### Uso consciente do Fabric (OBRIGATÓRIO)

O Fabric da organização cobra **por janela de consulta aberta** (cerca de 1 min por conexão), não pelo volume, e tem um teto de capacidade simultânea. Cada execução de `query` abre uma janela. Por isso:

1. **Planeje antes de executar.** Entenda o pedido, consulte `tables`/`describe` (vêm do cache local e não abrem janela) e escreva todas as consultas necessárias **antes** de rodar qualquer uma.
2. **Junte as consultas independentes num único `batch`**, em vez de várias `query` seguidas. Escreva os `.sql` (ou um `.json`) numa pasta temporária e rode tudo de uma vez. Use `query` avulsa só quando for realmente uma consulta, ou quando depender do resultado de outra. Nesse caso, faça um segundo batch.
3. **Sempre filtre.** Nunca `SELECT *` sem `WHERE` de período ou lista de contas, nem sem `TOP`. Há tabelas com milhões de linhas por dia. Para amostras, `TOP 10`. Para números, agregue no SQL (`GROUP BY`, `COUNT`, `SUM`) com filtro de período.
4. **Não explore por tentativa e erro no Fabric.** Confira nomes de colunas no `describe` antes. Uma consulta que falha por nome errado também abre janela.
5. **Erro 24801** (`[capacidade]`, exit code 3) = a organização está no teto naquele momento, não é erro da consulta. Explique isso à pessoa e **não insista em loop**: sugira tentar de novo em alguns minutos.
6. **Timeout** (padrão 300s): se estourar, refine a consulta (mais filtro, agregação) em vez de só aumentar o `--timeout`.
7. Se você não souber se uma tabela é grande, pergunte o período de interesse antes de consultar.

### Boas práticas ao consultar
- Dialeto é **T-SQL**: `TOP n` (não `LIMIT`), colchetes para nomes que começam com número ou têm caracteres especiais (`[2024_vendas]`), schema padrão `dbo`.
- Para extrações grandes, salve em arquivo (`--out` ou `batch --out-dir`) em vez de imprimir no terminal.
- Dados de clientes (CPF, conta, nome) são sensíveis: não reproduza listas inteiras na conversa sem necessidade; mostre amostras ou agregados.

### Quando a pessoa pede um script Python / notebook

Use as funções de `scripts/datalake.py`. Elas têm a mesma interface das funções antigas do time, mas **sem usuário, senha nem DSN**, porque usam o login do setup:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/fabric-readonly/scripts"))
from datalake import query_datalake, query_datalake_batch
dfs = query_datalake_batch({"ago": "SELECT ... WHERE ...", "set": "SELECT ... WHERE ..."})
```

- Todas as consultas no início do script, num único `query_datalake_batch`. Nunca loop de `query_datalake`.
- **Nunca escreva usuário, senha ou token no código.** Se a pessoa trouxer um script com credencial embutida, remova-a, migre para as funções da skill e avise que a credencial exposta deve ser trocada.
- O script roda com o `PY` da skill (já tem pandas) ou num ambiente com `pip install mssql-python azure-identity pandas`.
- Para **migrar** um script existente, siga a regra 6 de [BOAS_PRATICAS.md](BOAS_PRATICAS.md): mapear dependências, reordenar só o independente, trocar por um batch, remover credenciais e **comparar a saída antes e depois**.
- Login pessoal serve para uso interativo. Para rotina automática recorrente, oriente a combinar uma conta de serviço com o time.
- Parquet com datetime que vai subir para o Fabric: `df[c] = df[c].dt.tz_localize('UTC')` e `to_parquet(..., coerce_timestamps='ms')`.

## 4. Garantias de somente leitura

O script bloqueia antes de enviar ao servidor qualquer coisa que não seja **uma única** instrução `SELECT`/`WITH`, e recusa palavras como `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `CREATE`, `ALTER`, `TRUNCATE`, `EXEC`, `INTO`, `SET`, `DECLARE`, `COPY` etc. Além disso conecta com `ApplicationIntent=ReadOnly`, `autocommit=False` e sempre faz `ROLLBACK` no final. O próprio endpoint de Lakehouse já é somente leitura para as tabelas Delta.

**Nunca** contorne isso (não use outro cliente, `sqlcmd`, ou execute SQL de escrita por outro caminho). Se o usuário pedir alteração de dados, explique que esta skill é só leitura.

## 5. Problemas comuns

| Sintoma | Causa / ação |
|---|---|
| `Perfil ... não configurado` | Rodar `setup` (passo 2). |
| Login abre de novo toda vez | Rodar `login` uma vez; ele salva `~/.config/fabric-readonly/auth_record.json`. |
| `Login failed` / 18456 / not authorized | Conta sem acesso ao workspace/item, ou tenant errado (`--tenant`). |
| Host não encontrado / falha ao conectar | Cadeia copiada incompleta (o campo da tela vem truncado) ou VPN/firewall bloqueando a porta 1433. |
| `[capacidade]` / erro 24801 | Capacidade da organização no teto. Não é a consulta: esperar alguns minutos. Não repetir em loop. |
| `[erro] A consulta passou de Ns` | Consulta pesada demais: filtrar por período, agregar no SQL. Só aumentar `--timeout` se for realmente necessário. |
| `Invalid object name` | Ver nome exato com `tables`; usar `[colchetes]` e `dbo.` |
| Tabela recém-criada não aparece | O endpoint SQL sincroniza metadados com atraso de alguns minutos. |
