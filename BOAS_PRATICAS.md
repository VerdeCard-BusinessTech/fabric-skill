# Boas práticas de uso do DataLake / Microsoft Fabric

Objetivo: usar o Fabric de forma eficiente e **não estourar o limite de capacidade** da organização.

Esta skill já segue essas regras. Este documento explica o porquê e como aplicá-las nos seus próprios scripts.

---

## Contexto: como o Fabric cobra

A cobrança deixou de ser **"por consumo de CU"** e passou a ser **"por janela de consulta aberta"**. Cada solicitação abre uma janela de cerca de 1 minuto, e a cobrança é por janela aberta, não pelo volume processado dentro dela.

Consequência: o objetivo é **reduzir o número de janelas abertas**, não o tamanho de cada consulta.

Existe também um limite separado, de **capacidade computacional simultânea**. Quando ele estoura, aparece o erro:

```
Unable to complete the action because your organization's Fabric compute capacity has exceeded its limits (24801)
```

Esse erro **não é bug do seu código**: é a organização batendo no teto de capacidade naquele momento. Espere alguns minutos e tente de novo. A skill reconhece esse erro e avisa com uma mensagem clara.

---

## As 6 regras

### 1. Concentre as consultas no tempo
Rode todas as consultas ao DataLake o mais próximo possível umas das outras, **no início do script**. Não espalhe consultas pelo código com processamento pesado entre elas, porque cada uma abre uma nova janela.

### 2. Use `query_datalake_batch()`, nunca um loop de `query_datalake()`

Ruim:
```python
for mes in meses:
    dfs[mes] = query_datalake(f"SELECT ... WHERE anomes = {mes}")
```

Bom:
```python
queries = {mes: f"SELECT ... WHERE anomes = {mes}" for mes in meses}
dfs = query_datalake_batch(queries)   # dict {mes: DataFrame}
```

As consultas rodam **em paralelo**, com uma conexão por thread. O guardrail é `max_workers=20` por padrão. Não é um teto rígido, mas não aumente sem necessidade.

Pelo Claude ou pelo terminal, o equivalente é o comando `batch`.

### 3. Nunca coloque usuário e senha no código
Credencial escrita no código vaza: ela vai parar em e-mail, chat, Git e documentos compartilhados. Esta skill **não usa senha nenhuma**. Ela usa a conexão e o login Microsoft feitos no setup, e o token fica no cofre do sistema.

- **Análises e scripts que você roda manualmente:** use as funções da skill, que usam o seu login.
- **Rotinas automáticas recorrentes** (agendadas, rodando sozinhas): não use login pessoal, porque isso causa bloqueio de conta e dificulta rastrear o consumo. Combine com o time uma conta de serviço, com o segredo guardado num cofre ou em variável de ambiente, nunca no código.

### 4. Sempre filtre a consulta
Nunca puxe a tabela inteira. Use sempre `WHERE` com período (ex.: `dt_base = '2026-09-01'`) e/ou lista de contas (`WHERE conta IN (...)`). Algumas tabelas diárias têm **milhões de linhas por dia**.

Para conhecer uma tabela, use `TOP 10` ou peça a estrutura (comando `describe`, que não consulta o Fabric porque vem do cache). Para números, agregue no SQL (`GROUP BY`) em vez de trazer linhas para somar depois.

### 5. Parquet com coluna datetime para o Fabric
Se for subir um parquet com coluna `datetime64[ns]` para o Fabric, converta antes, senão a carga falha:

```python
df['minha_data'] = df['minha_data'].dt.tz_localize('UTC')
df.to_parquet('arquivo.parquet', coerce_timestamps='ms')
```

ns, us, ms sem timezone e DATE falham. Só funciona com timezone UTC + `ms`.

A skill é só de leitura e não sobe arquivos. A regra fica aqui para quando você preparar dados para carga por outro caminho.

### 6. Como migrar um script existente
Não basta trocar a chamada da função. Siga esta ordem:

1. **Mapeie as dependências** entre as consultas: qual consulta usa o resultado calculado de outra?
2. **Reordene só o que for independente.** Leve para o início apenas as consultas que não dependem de nada calculado depois do novo ponto.
3. **Troque** o conjunto de `query_datalake` por **uma** chamada de `query_datalake_batch`.
4. **Remova usuário, senha e DSN do código.** Importe as funções da skill (veja abaixo). A conexão vem do setup.
5. **Valide a saída antes e depois.** Rode a versão antiga e a nova e compare: mesmas colunas, mesma linhagem, e diferenças só onde são esperadas. Nunca assuma que ficou igual.

Consultas que dependem de resultados anteriores (ex.: lista de contas obtida em outra consulta) ficam num segundo batch, não no primeiro.

---

## Usando as funções no seu script

As funções `query_datalake` e `query_datalake_batch` estão em [`scripts/datalake.py`](scripts/datalake.py). A interface é a mesma das versões antigas (colunas em MAIÚSCULAS, mesmo retorno), mas **sem usuário, senha nem DSN**:

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/fabric-readonly/scripts"))
from datalake import query_datalake, query_datalake_batch

queries = {
    '202608': "SELECT conta, saldo FROM dbo.minha_tabela WHERE dt_base = '2026-08-31'",
    '202609': "SELECT conta, saldo FROM dbo.minha_tabela WHERE dt_base = '2026-09-30'",
}
dfs = query_datalake_batch(queries)
df_ago, df_set = dfs['202608'], dfs['202609']
```

Rode o script com o Python do ambiente da skill, que já tem `pandas`:
- macOS/Linux: `~/.config/fabric-readonly/venv/bin/python meu_script.py`
- Windows: `%USERPROFILE%\.config\fabric-readonly\venv\Scripts\python.exe meu_script.py`

Ou instale as dependências no seu próprio ambiente: `pip install mssql-python azure-identity pandas`.

Diferenças em relação às funções antigas:
- **Não precisa de DSN ODBC nem de driver instalado.**
- **Só leitura:** qualquer comando de escrita é bloqueado antes de ir ao Fabric.
- Erro de capacidade vira `FabricCapacityError`, com mensagem clara. Se uma consulta do batch falhar, as outras terminam e depois o erro lista quais falharam.
- Parâmetros extras opcionais: `profile=` (outro Lakehouse configurado), `timeout=` em segundos e `upper_columns=False` para manter os nomes originais.

Com **uma única** consulta não há ganho nem prejuízo em usar o batch. O benefício aparece com várias consultas juntas.

---

## Checklist rápido

- [ ] Todas as consultas estão juntas, no início do script?
- [ ] Estou usando `query_datalake_batch` e não um loop?
- [ ] O código está **sem usuário e senha**?
- [ ] Toda consulta tem filtro de período e/ou lista de contas?
- [ ] Parquet com datetime: `tz_localize('UTC')` + `coerce_timestamps='ms'`?
- [ ] Se migrei um script: comparei a saída antes e depois?
