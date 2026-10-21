# Novidades

Cada versão segue MAJOR.MINOR.PATCH:
- **PATCH** (1.4.**1**): correção;
- **MINOR** (1.**5**.0): novidade;
- **MAJOR** (**2**.0.0): mudança que exige alguma ação de quem usa.

O texto de cada versão aparece no chat quando a skill avisa que há atualização. Escreva em linguagem simples.

## 1.7.0 (2026-10-21)
- A skill agora **avisa sozinha quando há versão nova**: ao ser usada, ela confere o GitHub (no máximo 1x por hora).
- Novo pedido: *"atualize as skills do Fabric"*. Baixa a versão nova e mostra aqui o que mudou.
- Novo comando `versao`, que mostra as versões instaladas.

## 1.6.0 (2026-10-21)
- Toda mudança na skill agora passa por **revisão e aprovação** antes de chegar a você.
- **Verificação automática** bloqueia senhas, links de conexão e dados pessoais nas contribuições.
- Você pode **sugerir melhorias pelo próprio Claude**: ele oferece registrar o que você descobriu.

## 1.5.0 (2026-10-21)
- Integração com o **dicionário de tabelas** (skill `fabric-dicionario`): o Claude consulta o significado das tabelas antes de escrever o SQL.

## 1.4.1 (2026-10-15)
- Correção no Mac: a conexão voltou a funcionar depois de o Homebrew atualizar o OpenSSL para a versão 4.

## 1.4.0 (2026-10-07)
- **Guia rápido no chat** depois da instalação, com o que pedir, os padrões e o que fazer em caso de erro. Peça *"mostre o guia rápido do Fabric"*.

## 1.3.0 (2026-10-07)
- **Batch**: várias consultas juntas na mesma janela de cobrança do Fabric.
- Lista de tabelas e colunas em **cache local**, então explorar não gasta o Fabric.
- **Limite de 5 minutos** por consulta.
- Mensagem clara para o **erro 24801** (capacidade da organização).
- Funções `query_datalake` / `query_datalake_batch` para scripts Python, **sem senha**.

## 1.2.0 (2026-10-07)
- Instalação guiada para quem não é técnico, com detecção do sistema operacional e orientação para abrir o Claude Code.

## 1.1.0 (2026-10-06)
- Suporte a **macOS, Windows e Linux**.
- README com o passo a passo e prints de como pegar o link do Fabric.

## 1.0.0 (2026-10-06)
- Primeira versão: consulta **somente leitura** ao Fabric com login Microsoft, sem senha de banco.
