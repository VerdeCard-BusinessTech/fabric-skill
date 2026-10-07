#!/usr/bin/env python3
"""Cria o ambiente Python isolado da skill (uma vez só). Funciona em macOS, Linux e Windows.

  macOS/Linux:  python3 scripts/setup.py
  Windows:      py scripts\\setup.py
"""
import os
import subprocess
import sys
import venv
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit(f"Python 3.10+ é necessário (encontrado {sys.version.split()[0]}).")

home = Path(os.environ.get("FABRIC_RO_HOME", Path.home() / ".config" / "fabric-readonly"))
env_dir = home / "venv"
py = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

home.mkdir(parents=True, exist_ok=True)
if not py.exists():
    print(f"Criando ambiente em {env_dir} ...")
    venv.create(env_dir, with_pip=True)

subprocess.check_call([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"])
subprocess.check_call([str(py), "-m", "pip", "install", "-q", "mssql-python>=1.15", "azure-identity>=1.19",
                       "pandas>=2.0"])

query = Path(__file__).resolve().parent / "fabric_query.py"
print(f"OK: ambiente em {env_dir}")
print(f"Python da skill: {py}")
print(f"Próximo passo:   \"{py}\" \"{query}\" init")
