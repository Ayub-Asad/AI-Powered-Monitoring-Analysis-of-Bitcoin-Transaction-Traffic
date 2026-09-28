#!/usr/bin/env bash
set -euo pipefail
trap 'echo "Startup failed. Check README_OFFLINE.md, local files and port 8000." >&2' ERR
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$ROOT"
[[ -x .venv/bin/python ]] || { echo "Missing Linux .venv. Run bash install.sh first." >&2; exit 1; }
.venv/bin/python -B scripts/release.py python
.venv/bin/python -B scripts/build_dashboard.py
.venv/bin/python -B scripts/release.py verify
echo "Dashboard: http://127.0.0.1:8000 (first load takes time). Stop with Ctrl+C."
exec .venv/bin/python -B -m uvicorn app.main:app --app-dir "$ROOT/backend" --host 127.0.0.1 --port 8000
