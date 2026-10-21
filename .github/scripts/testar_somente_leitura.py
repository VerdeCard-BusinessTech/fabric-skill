"""Garante que o filtro de somente leitura continua bloqueando escrita (roda sem conexão)."""
import sys

sys.path.insert(0, "scripts")
from fabric_query import ReadOnlyViolation, assert_read_only  # noqa: E402

PERMITIDAS = [
    "SELECT TOP 5 * FROM dbo.[2024_vendas]",
    "WITH x AS (SELECT 1 AS a) SELECT * FROM x;",
    "SELECT 'drop table' AS t -- delete\n FROM y",
    "SELECT [update] FROM t",
]
BLOQUEADAS = [
    "DELETE FROM t",
    "UPDATE t SET a = 1",
    "INSERT INTO t VALUES (1)",
    "SELECT * INTO nova FROM t",
    "SELECT 1; DROP TABLE t",
    "EXEC sp_x",
    "/* x */ MERGE t USING s ON 1=1 WHEN MATCHED THEN DELETE;",
    "WITH x AS (SELECT 1 a) UPDATE t SET a = 1",
    "TRUNCATE TABLE t",
    "CREATE TABLE t (a int)",
]

erros = []
for sql in PERMITIDAS:
    try:
        assert_read_only(sql)
    except ReadOnlyViolation as e:
        erros.append(f"deveria PASSAR mas foi bloqueada: {sql!r} ({e})")
for sql in BLOQUEADAS:
    try:
        assert_read_only(sql)
        erros.append(f"deveria ser BLOQUEADA mas passou: {sql!r}")
    except ReadOnlyViolation:
        pass

if erros:
    print("🚨 O filtro de somente leitura quebrou:\n" + "\n".join(erros))
    sys.exit(1)
print(f"OK: {len(PERMITIDAS)} consultas permitidas e {len(BLOQUEADAS)} bloqueadas como esperado.")
