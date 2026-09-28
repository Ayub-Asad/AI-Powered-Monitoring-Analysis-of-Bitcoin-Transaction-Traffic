#!/usr/bin/env bash
set -euo pipefail
trap 'echo "Offline installation failed. See the error above and README_OFFLINE.md." >&2' ERR
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$ROOT"
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null || { echo "Python not found. Install CPython 3.13.14 with venv/ensurepip first." >&2; exit 1; }
"$PYTHON" -B scripts/release.py python
"$PYTHON" -B scripts/release.py verify
"$PYTHON" -B scripts/release.py verify-wheels
if [[ ! -d .venv ]]; then
    "$PYTHON" -m venv .venv || { echo "Cannot create .venv. Provision Python venv/ensurepip on the preparation machine." >&2; exit 1; }
fi
[[ -x .venv/bin/python ]] || { echo "Invalid .venv; move it aside and rerun install.sh." >&2; exit 1; }
.venv/bin/python -B scripts/release.py python
# Ignore user pip configuration; no index, cache, source build or network fallback.
PIP_CONFIG_FILE=/dev/null .venv/bin/python -m pip --isolated install --no-index --no-cache-dir --disable-pip-version-check --only-binary=:all: --find-links="$ROOT/wheels" -r backend/requirements-offline-lock.txt
.venv/bin/python -m pip --isolated check
.venv/bin/python -B scripts/verify_runtime.py
echo "Installed locally. Run: bash start.sh"
