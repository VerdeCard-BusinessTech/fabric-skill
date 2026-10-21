## 🚨 ATENÇÃO: este repositório é PÚBLICO

Tudo o que entra aqui fica visível para **qualquer pessoa na internet, para sempre**. Apagar depois **não resolve**: o histórico do Git e as cópias (forks) guardam tudo.

**Nunca inclua neste PR:**
- 🔑 **Senhas, tokens, chaves de API** ou qualquer credencial (inclusive de contas de serviço/robô)
- 🔗 **Links de conexão do Fabric** (`xxxx.datawarehouse.fabric.microsoft.com`)
- 👤 **Dados de clientes ou colaboradores**: CPF, CNPJ, nomes, contas, telefones, e-mails, matrículas
- 📊 **Resultados de consultas** com dados reais (prints, CSVs, exemplos copiados do Fabric)
- 🏢 IDs internos do Azure/Entra (tenant, usuário) ou e-mails corporativos

**Se você colocou alguma credencial por engano:** não basta apagar. Avise o responsável pelo repositório **imediatamente** e **troque a senha ou token**, porque ela já foi exposta.

Uma verificação automática bloqueia o PR quando encontra esses padrões, mas ela não pega tudo. **A responsabilidade é de quem abre o PR.**

---

## O que muda

<!-- Descreva em poucas linhas o que este PR adiciona ou corrige e por quê. -->

## Tipo de mudança

- [ ] Dicionário: tabela nova, coluna, regra de negócio ou correção
- [ ] Documentação (README, guias)
- [ ] Código (scripts)
- [ ] Instruções da skill (`SKILL.md`)

## Checklist

- [ ] **Não há senhas, tokens, links de conexão nem dados pessoais** neste PR (conferi arquivo por arquivo)
- [ ] Exemplos usam nomes genéricos (`dbo.minha_tabela`, `'2026-09-01'`), não dados reais
- [ ] Nomes de tabelas e colunas foram **conferidos no Fabric** (comando `describe` da fabric-readonly)
- [ ] Não inventei o significado de colunas: o que não sei ficou como "a confirmar"
- [ ] Se mexi em código: testei e o modo **somente leitura** continua intacto
