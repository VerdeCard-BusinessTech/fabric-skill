"""Funções para usar o Fabric em scripts Python e notebooks, SOMENTE LEITURA.

Mesma interface das funções query_datalake / query_datalake_batch usadas pelo time,
mas SEM usuário e senha: usam a conexão e o login Microsoft configurados no setup
da skill (perfil salvo em ~/.config/fabric-readonly).

    import sys, os
    sys.path.insert(0, os.path.expanduser("~/.claude/skills/fabric-readonly/scripts"))
    from datalake import query_datalake, query_datalake_batch

    queries = {
        "202608": "SELECT conta, saldo FROM dbo.minha_tabela WHERE dt_base = '2026-08-31'",
        "202609": "SELECT conta, saldo FROM dbo.minha_tabela WHERE dt_base = '2026-09-30'",
    }
    dfs = query_datalake_batch(queries)          # {nome: DataFrame}, tudo na mesma janela

Rode com o Python do ambiente da skill (já tem pandas), ou instale no seu ambiente:
    pip install mssql-python azure-identity pandas

Uso interativo / análises pontuais. Para rotinas automáticas recorrentes, não use login
pessoal: combine com o time uma conta de serviço.
"""
from __future__ import annotations

import pandas as pd

from fabric_query import (DEFAULT_WORKERS, FabricCapacityError, FabricError, ReadOnlyViolation,
                          assert_read_only, get_profile, run, run_batch)

__all__ = ["query_datalake", "query_datalake_batch",
           "FabricError", "FabricCapacityError", "ReadOnlyViolation"]


def _to_df(cols, rows, upper_columns: bool) -> pd.DataFrame:
    df = pd.DataFrame.from_records(rows, columns=cols)
    if upper_columns:
        df.columns = [str(c).upper() for c in df.columns]
    return df


def query_datalake(query: str, profile: str | None = None, upper_columns: bool = True,
                   timeout: int = 0) -> pd.DataFrame:
    """Executa UMA consulta e retorna um DataFrame.

    Para várias consultas, prefira query_datalake_batch: cada chamada desta função
    abre uma janela de cobrança no Fabric.

    profile       : perfil do setup (padrão: o perfil padrão)
    upper_columns : colunas em MAIÚSCULAS, como nas funções antigas do time
    timeout       : segundos por consulta (0 = sem limite)
    """
    _, prof = get_profile(profile)
    cols, rows, _ = run(prof, assert_read_only(query), max_rows=0, timeout=timeout)
    df = _to_df(cols, rows, upper_columns)
    print(f"[OK] Query executada — {df.shape[0]:,} linhas, {df.shape[1]} colunas")
    return df


def query_datalake_batch(queries, profile: str | None = None, max_workers: int = DEFAULT_WORKERS,
                         upper_columns: bool = True, timeout: int = 0):
    """Executa várias consultas em PARALELO, todas no mesmo instante, para concentrá-las
    na mesma janela de cobrança do Fabric e reduzir o tempo total.

    Uma conexão por thread (conexões não podem ser compartilhadas entre threads).

    queries     : lista de SQL, ou dict {nome: sql}
    max_workers : consultas simultâneas (padrão 20; guardrail contra estourar a capacidade
                  do Fabric. Não é teto rígido, mas não aumente sem necessidade)

    Retorna a lista de DataFrames (mesma ordem) ou dict {nome: DataFrame}, conforme a entrada.
    Se alguma consulta falhar, as outras terminam e depois é lançado um FabricError
    listando as que falharam (FabricCapacityError se for o erro 24801 de capacidade).
    """
    as_dict = isinstance(queries, dict)
    items = dict(queries) if as_dict else dict(enumerate(queries))
    _, prof = get_profile(profile)
    results = run_batch(prof, items, max_rows=0, timeout=timeout, max_workers=max_workers)

    out, errors = {}, {}
    for key in items:
        res = results[key]
        if isinstance(res, Exception):
            errors[key] = res
            continue
        out[key] = _to_df(res[0], res[1], upper_columns)
        print(f"[OK] Query '{key}' executada — {out[key].shape[0]:,} linhas, {out[key].shape[1]} colunas")

    if errors:
        detail = "; ".join(f"'{k}': {e}" for k, e in errors.items())
        cls = FabricCapacityError if all(isinstance(e, FabricCapacityError) for e in errors.values()) else FabricError
        raise cls(f"{len(errors)} de {len(items)} consultas falharam: {detail}")

    return out if as_dict else [out[i] for i in range(len(items))]
