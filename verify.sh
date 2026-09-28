#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$ROOT"
[[ -x .venv/bin/python ]] || { echo "Run bash install.sh first." >&2; exit 1; }
.venv/bin/python -B scripts/release.py verify
.venv/bin/python -m pip --isolated check
.venv/bin/python -B scripts/verify_runtime.py
