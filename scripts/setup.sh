#!/usr/bin/env bash
# Cria o ambiente Python isolado da skill (uma vez só).
set -euo pipefail
HOME_DIR="${FABRIC_RO_HOME:-$HOME/.config/fabric-readonly}"
mkdir -p "$HOME_DIR"
if [ ! -x "$HOME_DIR/venv/bin/python" ]; then
  python3 -m venv "$HOME_DIR/venv"
fi
"$HOME_DIR/venv/bin/pip" install -q --upgrade pip
"$HOME_DIR/venv/bin/pip" install -q "mssql-python>=1.15" "azure-identity>=1.19"
echo "OK: ambiente em $HOME_DIR/venv"
echo "Próximo passo: $HOME_DIR/venv/bin/python $(cd "$(dirname "$0")" && pwd)/fabric_query.py init"
