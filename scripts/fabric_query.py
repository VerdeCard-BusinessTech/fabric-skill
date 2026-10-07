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
  fabric_query.py batch a.sql b.sql [--json consultas.json] [--out-dir resultados/]

Em scripts Python/notebooks, use scripts/datalake.py (query_datalake / query_datalake_batch).
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
SCOPE = "https://database.windows.net/.default"
DEFAULT_TIMEOUT = 300          # segundos por consulta (0 = sem limite)
DEFAULT_WORKERS = 20           # guardrail de consultas simultâneas no batch
SCHEMA_TTL = 24 * 3600         # cache da estrutura das tabelas vale 24h


class FabricError(RuntimeError):
    """Erro com mensagem já amigável para o usuário."""


class ReadOnlyViolation(FabricError):
    pass


class FabricCapacityError(FabricError):
    pass


CAPACITY_MSG = ("A capacidade de processamento do Fabric da organização está no limite agora (erro 24801). "
                "Não é erro da sua consulta: espere alguns minutos e tente de novo. Para ajudar, junte as "
                "consultas num batch e filtre por período.")
TIMEOUT_MSG = ("A consulta passou de {s}s e foi cancelada. Filtre por período/lista de contas, agregue "
               "(GROUP BY) ou aumente o limite com --timeout.")


def _translate_error(exc: Exception, timeout: int) -> Exception:
    msg = str(exc)
    if "24801" in msg or "capacity has exceeded" in msg.lower():
        return FabricCapacityError(CAPACITY_MSG)
    if timeout and ("HYT00" in msg or "timeout expired" in msg.lower() or "query timeout" in msg.lower()):
        return FabricError(TIMEOUT_MSG.format(s=timeout))
    return exc

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
        raise ReadOnlyViolation("Consulta vazia.")
    if ";" in cleaned:
        raise ReadOnlyViolation("Bloqueado: apenas UMA instrução por execução (encontrei ';' no meio).")
    words = re.findall(r"[A-Za-z_]+", cleaned.upper())
    if words[0] not in ("SELECT", "WITH"):
        raise ReadOnlyViolation(f"Bloqueado: só SELECT/WITH são permitidos (começa com {words[0]}).")
    bad = sorted(FORBIDDEN.intersection(words))
    if bad:
        raise ReadOnlyViolation(f"Bloqueado: palavras-chave não permitidas em modo leitura: {', '.join(bad)}")
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
        raise FabricError(f"Perfil '{name}' não configurado. Perfis: {known}. Rode o comando 'setup' primeiro.")
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
    record = cred.authenticate(scopes=[SCOPE])
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_RECORD.write_text(record.serialize())
    os.chmod(AUTH_RECORD, 0o600)
    print(f"Login OK: {record.username} (tenant {record.tenant_id})")


def connect(profile: dict, device_code: bool = False, cred=None, timeout: int = DEFAULT_TIMEOUT):
    import mssql_python
    conn_str = (
        f"Server=tcp:{profile['server']},1433;"
        f"Database={profile['database']};"
        "Encrypt=yes;TrustServerCertificate=no;ApplicationIntent=ReadOnly;"
    )
    cred = cred or get_credential(profile.get("tenant"), device_code)
    # autocommit=False + rollback no final: nada é efetivado mesmo que algo escape do filtro
    conn = mssql_python.connect(conn_str, autocommit=False, token_provider=cred, timeout=60)
    if timeout:
        conn.timeout = timeout   # limite por consulta
    return conn


def run(profile: dict, sql: str, params=(), max_rows: int = 200, device_code: bool = False,
        timeout: int = DEFAULT_TIMEOUT, cred=None):
    """Executa UMA consulta (uma conexão = uma janela de cobrança no Fabric)."""
    try:
        conn = connect(profile, device_code, cred, timeout)
    except Exception as e:
        raise _translate_error(e, timeout) from e
    try:
        cur = conn.cursor()
        cur.execute(sql, params) if params else cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows + 1) if max_rows > 0 else cur.fetchall()
        truncated = max_rows > 0 and len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]
        return cols, [list(r) for r in rows], truncated
    except Exception as e:
        raise _translate_error(e, timeout) from e
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def run_batch(profile: dict, queries: dict, max_rows: int = 0, device_code: bool = False,
              timeout: int = DEFAULT_TIMEOUT, max_workers: int = DEFAULT_WORKERS) -> dict:
    """Executa várias consultas em paralelo, todas no mesmo instante, para caberem na mesma
    janela de cobrança do Fabric. Uma conexão por thread (conexões não são thread-safe).

    Todas as consultas passam pelo filtro de leitura ANTES de qualquer execução.
    Retorna {nome: (cols, rows, truncated)} ou {nome: Exception} para as que falharam.
    """
    from concurrent.futures import ThreadPoolExecutor

    checked = {name: assert_read_only(sql) for name, sql in queries.items()}
    cred = get_credential(profile.get("tenant"), device_code)
    cred.get_token(SCOPE)   # resolve o login antes de abrir as threads (evita N janelas de login)

    def one(item):
        name, sql = item
        try:
            return name, run(profile, sql, (), max_rows, timeout=timeout, cred=cred)
        except Exception as e:  # um erro não derruba as outras consultas
            return name, e

    workers = max(1, min(max_workers or len(checked), len(checked)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(ex.map(one, checked.items()))


# ---------------------------------------------------------------- cache da estrutura (tabelas/colunas)

SCHEMA_SQL = """
SELECT c.TABLE_SCHEMA, c.TABLE_NAME, t.TABLE_TYPE, c.COLUMN_NAME, c.DATA_TYPE,
       c.CHARACTER_MAXIMUM_LENGTH, c.IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS c
JOIN INFORMATION_SCHEMA.TABLES t ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
WHERE c.TABLE_SCHEMA NOT IN ('sys', 'queryinsights', 'INFORMATION_SCHEMA')
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
"""


def load_schema(name: str, profile: dict, refresh: bool = False, device_code: bool = False) -> dict:
    """Estrutura de todas as tabelas numa ÚNICA consulta, guardada por 24h.
    Assim listar tabelas e descrever colunas não abre uma janela no Fabric a cada pedido."""
    import time
    path = CONFIG_DIR / f"schema_{re.sub(r'[^A-Za-z0-9_-]', '_', name)}.json"
    if not refresh and path.exists():
        data = json.loads(path.read_text())
        if time.time() - data.get("fetched_at", 0) < SCHEMA_TTL:
            return data
    _, rows, _ = run(profile, SCHEMA_SQL, max_rows=0, device_code=device_code)
    tables: dict = {}
    for schema, table, ttype, col, dtype, size, nullable in rows:
        t = tables.setdefault(f"{schema}.{table}", {"schema": schema, "table": table, "type": ttype, "columns": []})
        t["columns"].append([col, dtype, size, nullable])
    data = {"fetched_at": time.time(), "tables": tables}
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False))
    return data


def find_table(schema_data: dict, ref: str) -> dict:
    schema, _, table = ref.replace("[", "").replace("]", "").rpartition(".")
    hits = [t for t in schema_data["tables"].values()
            if t["table"].lower() == table.lower() and (not schema or t["schema"].lower() == schema.lower())]
    if not hits:
        raise FabricError(f"Tabela '{ref}' não encontrada. Use 'tables --like' para procurar "
                          "ou '--refresh' se ela foi criada há pouco.")
    return hits[0]


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
            sp.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                            help=f"segundos por consulta (padrão {DEFAULT_TIMEOUT}; 0 = sem limite)")

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
    s = sub.add_parser("tables", help="listar tabelas/views (usa cache de 24h)")
    common(s)
    s.add_argument("--like", help="filtro por nome (contém)")
    s.add_argument("--refresh", action="store_true", help="recarregar a estrutura do Fabric")
    s = sub.add_parser("describe", help="colunas de uma ou mais tabelas (usa cache de 24h)")
    common(s)
    s.add_argument("table", nargs="+", help="tabela ou schema.tabela (pode passar várias)")
    s.add_argument("--refresh", action="store_true", help="recarregar a estrutura do Fabric")
    s = sub.add_parser("query", help="executar SELECT")
    common(s)
    s.add_argument("sql", nargs="?")
    s.add_argument("--file")
    s = sub.add_parser("batch", help="várias consultas em paralelo, na mesma janela do Fabric")
    common(s)
    s.add_argument("files", nargs="*", help="arquivos .sql (o nome do arquivo vira o nome do resultado)")
    s.add_argument("--json", help='arquivo JSON {"nome": "SELECT ..."}')
    s.add_argument("--out-dir", help="salvar cada resultado como <nome>.csv/.json nesta pasta")
    s.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                   help=f"consultas simultâneas (padrão {DEFAULT_WORKERS}; não aumente sem necessidade)")

    args = p.parse_args()
    try:
        dispatch(args)
    except ReadOnlyViolation as e:
        print(f"[bloqueado] {e}", file=sys.stderr)
        sys.exit(2)
    except FabricCapacityError as e:
        print(f"[capacidade] {e}", file=sys.stderr)
        sys.exit(3)
    except FabricError as e:
        print(f"[erro] {e}", file=sys.stderr)
        sys.exit(1)


def dispatch(args):

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
        data = load_schema(name, profile, args.refresh, args.device_code)
        like = (args.like or "").lower()
        rows = [[t["schema"], t["table"], t["type"], len(t["columns"])]
                for t in data["tables"].values() if like in t["table"].lower()]
        limit = args.max_rows if args.max_rows > 0 else len(rows)
        emit(["schema", "tabela", "tipo", "colunas"], rows[:limit], len(rows) > limit, args)
        return

    if args.cmd == "describe":
        data = load_schema(name, profile, args.refresh, args.device_code)
        for i, ref in enumerate(args.table):
            t = find_table(data, ref)
            if len(args.table) > 1:
                print(f"{'' if i == 0 else chr(10)}### {t['schema']}.{t['table']} ({t['type']})")
            emit(["coluna", "tipo", "tam", "nulo"], t["columns"], False, args)
        return

    if args.cmd == "query":
        sql = Path(args.file).read_text() if args.file else (args.sql or sys.stdin.read())
        sql = assert_read_only(sql)
        emit(*run(profile, sql, (), args.max_rows, args.device_code, args.timeout), args)
        return

    if args.cmd == "batch":
        queries = {}
        if args.json:
            queries.update(json.loads(Path(args.json).read_text()))
        for f in args.files:
            queries[Path(f).stem] = Path(f).read_text()
        if not queries:
            raise FabricError("Nenhuma consulta. Passe arquivos .sql ou --json consultas.json.")
        results = run_batch(profile, queries, args.max_rows, args.device_code, args.timeout, args.workers)
        if args.out_dir:
            Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        failed = 0
        for qname in queries:
            res = results[qname]
            if isinstance(res, Exception):
                failed += 1
                kind = "capacidade" if isinstance(res, FabricCapacityError) else "erro"
                print(f"### {qname}: [{kind}] {res}", file=sys.stderr)
                continue
            cols, rows, truncated = res
            if args.out_dir:
                ext = "json" if args.format == "json" else "csv"
                out = Path(args.out_dir) / f"{qname}.{ext}"
                out.write_text(render(cols, rows, "json" if ext == "json" else "csv"))
                print(f"### {qname}: {len(rows)} linhas -> {out}" + (" (TRUNCADO)" if truncated else ""))
            else:
                print(f"\n### {qname} ({len(rows)} linhas{', TRUNCADO' if truncated else ''})")
                print(render(cols, rows, args.format))
        print(f"\n{len(queries) - failed}/{len(queries)} consultas OK numa única rodada.", file=sys.stderr)
        if failed:
            sys.exit(1)


if __name__ == "__main__":
    main()
