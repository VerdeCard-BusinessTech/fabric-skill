# Como contribuir

Esta skill evolui com o uso: se você descobriu o significado de uma coluna, uma regra de negócio, um erro ou uma melhoria, contribua.

## 🚨 Antes de tudo: o repositório é PÚBLICO

Qualquer pessoa na internet lê tudo o que entra aqui, e o histórico do Git guarda tudo mesmo depois de apagado. **Nunca inclua:**

- 🔑 senhas, tokens, chaves ou credenciais de qualquer conta (inclusive contas de serviço/robô)
- 🔗 links de conexão do Fabric (`xxxx.datawarehouse.fabric.microsoft.com`)
- 👤 dados de clientes ou colaboradores: CPF, CNPJ, nomes, contas, telefones, e-mails, matrículas
- 📊 resultados de consultas com dados reais (prints, CSVs, exemplos)
- 🏢 IDs do Azure/Entra (tenant, usuário) ou e-mails corporativos

**Vazou uma credencial?** Apagar não resolve. Avise o responsável e **troque a senha ou token imediatamente**.

Uma verificação automática roda em todo PR e bloqueia esses padrões, mas ela não pega tudo. A responsabilidade é de quem contribui.

## Três formas de contribuir

### 1. Pedindo ao Claude (mais fácil)
Enquanto usa a skill, diga algo como *"registre isso no dicionário"* ou *"sugira essa melhoria na skill"*.
- **Com conta no GitHub configurada** (`gh auth login`): o Claude mostra a mudança, pede sua confirmação e abre o PR.
- **Sem GitHub:** o Claude escreve a sugestão pronta para você mandar ao responsável.

### 2. Abrindo uma issue
Na aba **Issues** do repositório → **New issue** → **Sugestão ou correção**.

### 3. Abrindo um PR
1. Faça um *fork* do repositório e crie um branch.
2. Faça a mudança. Para o dicionário, siga o `MODELO.md`.
3. Abra o PR e **preencha o checklist** do modelo.

## Aprovação

- Toda mudança no `main` passa por **PR com aprovação do responsável** (arquivo `.github/CODEOWNERS`).
- A verificação automática (credenciais, dados pessoais e, na skill de conexão, o filtro de somente leitura) precisa passar.
- Depois de aprovada, a mudança chega a todos no próximo `git pull`.

## Versões e atualizações

- A versão fica no arquivo `VERSION` (MAJOR.MINOR.PATCH), e as novidades ficam no `CHANGELOG.md`.
- Para uma mudança chegar a todos como atualização, **no mesmo PR**:
  - aumente o `VERSION`: PATCH para correção, MINOR para novidade, MAJOR se exigir ação de quem usa;
  - escreva no topo do `CHANGELOG.md` o que muda, **em linguagem simples**. É esse texto que aparece no chat.
- Quando o PR entra no `main`, a Release do GitHub é criada automaticamente.
- Quem usa é avisado no chat: a skill confere o GitHub ao ser acionada, no máximo 1x por hora, e oferece atualizar.
- Quer receber e-mail a cada versão? No GitHub: **Watch → Custom → Releases**.
