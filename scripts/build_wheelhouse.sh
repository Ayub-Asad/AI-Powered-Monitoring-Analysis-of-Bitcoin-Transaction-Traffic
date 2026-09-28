#!/usr/bin/env bash
# ONLINE preparation only. Run on the SAME Linux architecture/distribution as the target.
set -euo pipefail
trap 'echo "Wheelhouse preparation failed; do not ship it as verified." >&2' ERR
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$ROOT"
[[ "$(uname -s)" == Linux ]] || { echo "Use a compatible Linux machine, not Windows/Git Bash." >&2; exit 1; }
PYTHON="${PYTHON:-python3}"
"$PYTHON" -B scripts/release.py python
[[ ! -e wheels ]] || { echo "wheels already exists; move it aside before building a fresh wheelhouse." >&2; exit 1; }
mkdir wheels
"$PYTHON" -m pip --isolated download --only-binary=:all: --dest wheels -r backend/requirements-offline-lock.txt
"$PYTHON" -B scripts/release.py wheels
# Prove dependency closure by installing locally without an index, then load the frozen model.
bash install.sh
echo "Wheelhouse installed and runtime checked on this Linux machine. Complete the browser/network-disabled checklist."
