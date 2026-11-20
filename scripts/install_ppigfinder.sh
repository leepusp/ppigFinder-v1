#!/usr/bin/env bash
# Install the ppigFinder desktop without installing AF3 inference/weights.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -n "${PPIG_PYTHON:-}" ]]; then
  PY="$PPIG_PYTHON"
elif command -v python3.11 >/dev/null; then
  PY=python3.11
elif command -v python3.12 >/dev/null; then
  PY=python3.12
elif command -v python3.13 >/dev/null; then
  PY=python3.13
elif command -v python3 >/dev/null; then
  PY=python3
else
  echo 'ERROR: Python >= 3.11 not found. Install Python 3.11+ first.' >&2; exit 2
fi
"$PY" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"ERROR: Python 3.11+ required, found {sys.version.split()[0]}.")
print('PYTHON_OK:', sys.version.split()[0])
PY
if [[ ! -d .venv ]]; then
  "$PY" -m venv .venv
fi
VENV="${ROOT}/.venv/bin/python"
"$VENV" -m pip install --upgrade pip
"$VENV" -m pip install -e '.[gui,recommended]'
"$VENV" -m pip check
"$VENV" -m ppigfinder.integrations.af3.cli doctor --mode wrapper
echo 'PPIGFINDER_INSTALL=PASS'
echo 'Launch with: .venv/bin/python main.py'
echo 'AF3 guide: docs/user_manual/af3_local_installation.md'
