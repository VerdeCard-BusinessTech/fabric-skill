"""Bloqueia credenciais e dados pessoais num repositório público.

Roda em todo PR e em todo push no main. Varre os arquivos de texto do repositório
(não só o diff), para pegar também o que já tiver entrado por engano.
"""
import re
import sys
from pathlib import Path

IGNORAR_DIRS = {".git", "node_modules", "__pycache__"}
IGNORAR_ARQUIVOS = {".github/scripts/verificar_segredos.py"}
EXTENSOES_BINARIAS = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".zip"}

PADROES = [
    ("Link de conexão do Fabric",
     r"\b[a-z0-9]{12,}-[a-z0-9]{12,}\.datawarehouse\.fabric\.microsoft\.com"),
    ("Senha em string de conexão", r"(?i)\b(pwd|password)\s*=\s*[^;\s{}<>\"']{3,}"),
    ("Senha em código", r"(?i)\b(password|senha|passwd|pwd)\s*[:=]\s*[\"'][^\"'\s]{4,}[\"']"),
    ("Token do GitHub", r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}"),
    ("Chave privada", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("Token JWT", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("Chave do Azure Storage", r"(?i)AccountKey=[A-Za-z0-9+/=]{20,}"),
    ("Segredo de aplicativo Azure", r"(?i)client_?secret\s*[:=]\s*[\"'][^\"']{8,}[\"']"),
    ("CPF formatado", r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    ("CNPJ formatado", r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    ("E-mail corporativo", r"(?i)\b[\w.+-]+@(lojasqueroquero|queroquero|verdecard)[\w.-]*\.(com|onmicrosoft\.com)(\.br)?\b"),
    ("GUID (tenant/usuário do Entra)", r"(?i)\b(tenant|tenant_id|tid|oid)\b[\"'\s:=]+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
]

# Permitidos explicitamente (públicos ou exemplos genéricos)
PERMITIDOS = [
    r"xxxx\.datawarehouse",
    r"<host>\.datawarehouse",
]


def arquivos():
    for p in Path(".").rglob("*"):
        if not p.is_file() or any(part in IGNORAR_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in EXTENSOES_BINARIAS or p.as_posix() in IGNORAR_ARQUIVOS:
            continue
        yield p


achados = []
for arq in arquivos():
    try:
        linhas = arq.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        continue
    for n, linha in enumerate(linhas, 1):
        if any(re.search(ok, linha) for ok in PERMITIDOS):
            continue
        for nome, padrao in PADROES:
            if re.search(padrao, linha):
                trecho = linha.strip()
                trecho = trecho[:60] + "..." if len(trecho) > 60 else trecho
                achados.append(f"{arq}:{n}: {nome}  ->  {trecho}")

if achados:
    print("🚨 Possíveis credenciais ou dados pessoais encontrados (repositório PÚBLICO):\n")
    print("\n".join(achados))
    print("\nRemova antes de juntar o PR. Se for credencial real, ela já foi exposta: TROQUE-A.")
    print("Falso positivo? Explique no PR para o responsável avaliar.")
    sys.exit(1)

print("OK: nenhuma credencial ou dado pessoal encontrado.")
