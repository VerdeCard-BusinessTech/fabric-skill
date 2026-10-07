#!/usr/bin/env python3
"""Consulta SOMENTE LEITURA ao SQL analytics endpoint do Microsoft Fabric (Lakehouse/Warehouse).

Autenticação: Microsoft Entra ID (login no navegador, token em cache no Keychain).
Driver: mssql-python (não precisa de ODBC instalado).

Uso:
  fabric_query.py setup --profile neg_bt --server <host>.datawarehouse.fabric.microsoft.com --database Neg_BT
  fabric_query.py login   [--profile neg_bt] [--device-code]
  fabric_query.py test    [--profile neg_bt]
  fabric_query.py tables  [--profile neg_bt] [--like vendas]
  fabric_query.py describe <tabela> [--profile neg_bt]
  fabric_query.py query "SELECT TOP 10 * FROM dbo.x" [--max-rows 200] [--format table|csv|json] [--out arq.csv]
  fabric_query.py query --file consulta.sql
"""
import argparse
import csv
import datetime as dt
import decimal
import io
import json
import os
import re
import sys
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("FABRIC_RO_HOME", Path.home() / ".config" / "fabric-readonly"))
CONFIG_FILE = CONFIG_DIR / "config.json"
AUTH_RECORD = CONFIG_DIR / "auth_record.json"
CACHE_NAME = "fabric-readonly"

# ---------------------------------------------------------------- read-only guard

FORBIDDEN = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "CREATE", "ALTER", "TRUNCATE",
    "EXEC", "EXECUTE", "GRANT", "REVOKE", "DENY", "INTO", "BULK", "OPENROWSET",
    "OPENQUERY", "OPENDATASOURCE", "COPY", "RENAME", "BACKUP", "RESTORE", "KILL",
    "SHUTDOWN", "RECONFIGURE", "DBCC", "USE", "SET", "DECLARE", "BEGIN", "COMMIT",
    "ROLLBACK", "SAVE", "WAITFOR", "UPDATETEXT", "WRITETEXT", "OUTPUT",
}


def _strip_sql(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)        # /* bloco */
    sql = re.sub(r"--[^\n]*", " ", sql)                      # -- linha
    sql = re.sub(r"N?'(?:[^']|'')*'", "''", sql)             # 'literais'
    sql = re.sub(r"\[[^\]]*\]", "[x]", sql)                  # [identificadores]
    sql = re.sub(r'"[^"]*"', '"x"', sql)                     # "identificadores"
    return sql


def assert_read_only(sql: str) -> str:
    cleaned = _strip_sql(sql).strip().rstrip(";").strip()
    if not cleaned:
        raise SystemExit("Consulta vazia.")
    if ";" in cleaned:
        raise SystemExit("Bloqueado: apenas UMA instrução por execução (encontrei ';' no meio).")
    words = re.findall(r"[A-Za-z_]+", cleaned.upper())
    if words[0] not in ("SELECT", "WITH"):
        raise SystemExit(f"Bloqueado: só SELECT/WITH são permitidos (começa com {words[0]}).")
    bad = sorted(FORBIDDEN.intersection(words))
    if bad:
        raise SystemExit(f"Bloqueado: palavras-chave não permitidas em modo leitura: {', '.join(bad)}")
    return sql.strip().rstrip(";")


# ---------------------------------------------------------------- config

def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {"default": None, "profiles": {}}


def get_profile(name: str | None) -> tuple[str, dict]:
    cfg = load_config()
    # variáveis de ambiente têm prioridade
    if os.environ.get("FABRIC_SQL_SERVER") and os.environ.get("FABRIC_SQL_DATABASE"):
        return "env", {"server": os.environ["FABRIC_SQL_SERVER"], "database": os.environ["FABRIC_SQL_DATABASE"],
                       "tenant": os.environ.get("FABRIC_TENANT_ID")}
    name = name or cfg.get("default")
    if not name or name not in cfg["profiles"]:
        known = ", ".join(cfg["profiles"]) or "(nenhum)"
        raise SystemExit(f"Perfil '{name}' não configurado. Perfis: {known}. Rode o comando 'setup' primeiro.")
    return name, cfg["profiles"][name]


def normalize_server(server: str) -> str:
    server = server.strip()
    server = re.sub(r"^tcp:", "", server, flags=re.I)
    server = re.sub(r",\d+$", "", server)
    if not server.endswith(".fabric.microsoft.com"):
        print("Aviso: o host não termina em .fabric.microsoft.com — confira se copiou a cadeia inteira "
              "(o campo na tela do Fabric aparece truncado com '...').", file=sys.stderr)
    return server


# ---------------------------------------------------------------- auth / conexão

def has_browser() -> bool:
    """Linux sem interface gráfica (servidor, SSH, WSL sem GUI) não consegue abrir o navegador."""
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def get_credential(tenant: str | None, device_code: bool = False):
    from azure.identity import (AuthenticationRecord, DeviceCodeCredential,
                                InteractiveBrowserCredential, TokenCachePersistenceOptions)
    # Token criptografado: Keychain (macOS), DPAPI (Windows), libsecret (Linux).
    # Linux sem libsecret (servidor/WSL) cai para arquivo protegido só pelas permissões do usuário.
    cache = TokenCachePersistenceOptions(name=CACHE_NAME,
                                         allow_unencrypted_storage=sys.platform.startswith("linux"))
    device_code = device_code or not has_browser()
    record = None
    if AUTH_RECORD.exists():
        record = AuthenticationRecord.deserialize(AUTH_RECORD.read_text())
    kwargs = {"cache_persistence_options": cache, "authentication_record": record}
    if tenant:
        kwargs["tenant_id"] = tenant
    if device_code:
        return DeviceCodeCredential(**kwargs)
    return InteractiveBrowserCredential(**kwargs)


def do_login(tenant: str | None, device_code: bool) -> None:
    cred = get_credential(tenant, device_code)
    record = cred.authenticate(scopes=["https://database.windows.net/.default"])
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_RECORD.write_text(record.serialize())
    os.chmod(AUTH_RECORD, 0o600)
    print(f"Login OK: {record.username} (tenant {record.tenant_id})")


def connect(profile: dict, device_code: bool = False):
    import mssql_python
    conn_str = (
        f"Server=tcp:{profile['server']},1433;"
        f"Database={profile['database']};"
        "Encrypt=yes;TrustServerCertificate=no;ApplicationIntent=ReadOnly;"
    )
    cred = get_credential(profile.get("tenant"), device_code)
    # autocommit=False + rollback no final: nada é efetivado mesmo que algo escape do filtro
    return mssql_python.connect(conn_str, autocommit=False, token_provider=cred, timeout=60)


def run(profile: dict, sql: str, params=(), max_rows: int = 200, device_code: bool = False):
    conn = connect(profile, device_code)
    try:
        cur = conn.cursor()
        cur.execute(sql, params) if params else cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows + 1) if max_rows > 0 else cur.fetchall()
        truncated = max_rows > 0 and len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]
        return cols, [list(r) for r in rows], truncated
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


# ---------------------------------------------------------------- saída

def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, (dt.date, dt.datetime, dt.time)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        s = format(v, "f")
        return (s.rstrip("0").rstrip(".") or "0") if "." in s else s
    if isinstance(v, bytes):
        return v.hex()
    return str(v)


def render(cols, rows, fmt: str) -> str:
    if fmt == "json":
        return json.dumps([dict(zip(cols, map(_fmt, r))) for r in rows], ensure_ascii=False, indent=2)
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        w.writerows([[_fmt(v) for v in r] for r in rows])
        return buf.getvalue()
    # tabela markdown, células longas cortadas
    def cell(v):
        s = _fmt(v).replace("|", "\\|").replace("\n", " ")
        return s if len(s) <= 60 else s[:57] + "..."
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def emit(cols, rows, truncated, args):
    text = render(cols, rows, args.format)
    if args.out:
        Path(args.out).write_text(text if args.format != "table" else render(cols, rows, "csv"))
        print(f"{len(rows)} linhas salvas em {args.out}" + (" (TRUNCADO pelo --max-rows)" if truncated else ""))
        return
    print(text)
    print(f"\n({len(rows)} linhas{'; TRUNCADO — use --max-rows maior ou agregue' if truncated else ''})",
          file=sys.stderr)


# ---------------------------------------------------------------- onboarding

GUIDE = Path(__file__).resolve().parent.parent / "guia" / "index.html"

GUIDE_STEPS = """
Como pegar o link de conexão do Fabric (guia com prints: {guide})

  1. Abra app.fabric.microsoft.com e clique no workspace (ex.: Neg_BT)
     em "Acesso rápido > Workspaces recentes".
  2. Na lista de itens, abra o item do tipo "Lakehouse" (casinha azul).
     O nome dele é o NOME DO BANCO.
  3. Clique na ENGRENAGEM (Configurações) na barra do Lakehouse.
  4. No menu lateral, clique em "Ponto de extremidade de análise de SQL"
     e use o BOTÃO DE COPIAR ao lado de "Cadeia de conexão SQL".
     (o texto na tela vem cortado com "..."; copie pelo botão)
     O link termina em .datawarehouse.fabric.microsoft.com

Não precisa de senha: o login é feito no navegador com sua conta Microsoft.
"""


def open_guide() -> None:
    print(GUIDE_STEPS.format(guide=GUIDE))
    if GUIDE.exists() and has_browser():
        import webbrowser
        webbrowser.open(GUIDE.as_uri())


def save_profile(name, server, database, tenant=None, make_default=False) -> None:
    cfg = load_config()
    cfg["profiles"][name] = {"server": normalize_server(server), "database": database, "tenant": tenant}
    if make_default or not cfg.get("default"):
        cfg["default"] = name
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    print(f"Perfil '{name}' salvo em {CONFIG_FILE} (padrão: {cfg['default']})")


def init_wizard(device_code: bool) -> None:
    open_guide()
    server = ""
    while not re.search(r"\.fabric\.microsoft\.com(,\d+)?$", server):
        server = input("Cole o link de conexão SQL: ").strip()
        if not re.search(r"\.fabric\.microsoft\.com(,\d+)?$", server):
            print("  Esse link não termina em .fabric.microsoft.com. Copie pelo botão de copiar e tente de novo.")
    database = ""
    while not database:
        database = input("Nome do Lakehouse (ex.: Neg_BT): ").strip()
    default_name = re.sub(r"\W+", "_", database).lower()
    name = input(f"Nome do perfil [{default_name}]: ").strip() or default_name
    save_profile(name, server, database, make_default=True)
    print("\nAbrindo o login da Microsoft no navegador..." if has_browser() and not device_code
          else "\nSiga as instruções abaixo para entrar com sua conta Microsoft:")
    do_login(None, device_code)
    _, rows, _ = run(load_config()["profiles"][name], "SELECT DB_NAME(), SUSER_SNAME()")
    print(f"\nTudo pronto! Conectado em {rows[0][0]} como {rows[0][1]}.")


# ---------------------------------------------------------------- CLI

def main():
    # console do Windows não é UTF-8 por padrão (acentos e tabelas quebrariam)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Fabric SQL endpoint — somente leitura")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, output=True):
        sp.add_argument("--profile")
        sp.add_argument("--device-code", action="store_true", help="login por código (sem abrir navegador)")
        if output:
            sp.add_argument("--max-rows", type=int, default=200, help="0 = sem limite")
            sp.add_argument("--format", choices=["table", "csv", "json"], default="table")
            sp.add_argument("--out", help="salvar resultado em arquivo")

    s = sub.add_parser("setup", help="salvar perfil de conexão")
    s.add_argument("--profile", required=True)
    s.add_argument("--server", required=True, help="cadeia de conexão SQL copiada do Fabric")
    s.add_argument("--database", required=True, help="nome do Lakehouse/Warehouse (ex.: Neg_BT)")
    s.add_argument("--tenant", help="tenant id do Entra (opcional)")
    s.add_argument("--default", action="store_true", help="tornar perfil padrão")

    sub.add_parser("guia", help="abrir o guia com prints de como pegar o link")
    s = sub.add_parser("init", help="assistente interativo de primeira configuração")
    s.add_argument("--device-code", action="store_true")

    s = sub.add_parser("login", help="autenticar e guardar sessão")
    common(s, output=False)
    s = sub.add_parser("profiles", help="listar perfis")
    s = sub.add_parser("test", help="testar conexão")
    common(s, output=False)
    s = sub.add_parser("tables", help="listar tabelas/views")
    common(s)
    s.add_argument("--like", help="filtro por nome (contém)")
    s = sub.add_parser("describe", help="colunas de uma tabela")
    common(s)
    s.add_argument("table", help="tabela ou schema.tabela")
    s = sub.add_parser("query", help="executar SELECT")
    common(s)
    s.add_argument("sql", nargs="?")
    s.add_argument("--file")

    args = p.parse_args()

    if args.cmd == "setup":
        save_profile(args.profile, args.server, args.database, args.tenant, args.default)
        return

    if args.cmd == "guia":
        open_guide()
        return

    if args.cmd == "init":
        init_wizard(args.device_code)
        return

    if args.cmd == "profiles":
        cfg = load_config()
        for n, pr in cfg["profiles"].items():
            print(f"{'*' if n == cfg.get('default') else ' '} {n}: {pr['database']} @ {pr['server']}")
        return

    name, profile = get_profile(args.profile)

    if args.cmd == "login":
        do_login(profile.get("tenant"), args.device_code)
        return

    if args.cmd == "test":
        cols, rows, _ = run(profile, "SELECT DB_NAME() AS banco, SUSER_SNAME() AS usuario, "
                                     "@@VERSION AS versao", device_code=args.device_code)
        print(f"Conectado ({name}): banco={rows[0][0]} usuario={rows[0][1]}")
        return

    if args.cmd == "tables":
        sql = ("SELECT TABLE_SCHEMA AS [schema], TABLE_NAME AS tabela, TABLE_TYPE AS tipo "
               "FROM INFORMATION_SCHEMA.TABLES")
        params = ()
        if args.like:
            sql += " WHERE TABLE_NAME LIKE ?"
            params = (f"%{args.like}%",)
        sql += " ORDER BY 1, 2"
        emit(*run(profile, sql, params, args.max_rows, args.device_code), args)
        return

    if args.cmd == "describe":
        schema, _, table = args.table.rpartition(".")
        sql = ("SELECT COLUMN_NAME AS coluna, DATA_TYPE AS tipo, CHARACTER_MAXIMUM_LENGTH AS tam, "
               "IS_NULLABLE AS nulo FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?")
        params = [table.strip("[]")]
        if schema:
            sql += " AND TABLE_SCHEMA = ?"
            params.append(schema.strip("[]"))
        sql += " ORDER BY ORDINAL_POSITION"
        emit(*run(profile, sql, tuple(params), args.max_rows, args.device_code), args)
        return

    if args.cmd == "query":
        sql = Path(args.file).read_text() if args.file else (args.sql or sys.stdin.read())
        sql = assert_read_only(sql)
        emit(*run(profile, sql, (), args.max_rows, args.device_code), args)


if __name__ == "__main__":
    main()
