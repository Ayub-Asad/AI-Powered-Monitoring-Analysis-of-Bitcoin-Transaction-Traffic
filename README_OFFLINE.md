# Offline Bitcoin Transaction Intelligence Platform

Linux packaging prepared; execution verification pending.

This prototype serves a synthetic Bitcoin investigation dashboard entirely on
localhost. No cloud, account, Node, CDN, online GeoIP or blockchain connection is
required. Synthetic anomalies are investigative examples, not criminal evidence.

## Requirements and supported environment

- **CPython 3.13.14 exactly**, including `venv`, `ensurepip` and pip. The frozen
  trusted model enforces this patch version and its recorded package versions.
  Other Python versions are not supported for this release; do not bypass the
  compatibility check or retrain the model to make it load.
- Intended Linux target: 64-bit glibc Linux, with Bash and a modern local browser.
  Prepare wheels on the same distribution, architecture and Python as the target.
  A Linux distribution/version has NOT yet been certified. Alpine/musl, ARM and
  free-threaded Python are not verified targets.
- Windows with CPython 3.13.14 is the tested development environment. Linux wheel
  availability, installation and cross-OS artifact compatibility remain pending.
- Provision the OS, Python/venv and browser BEFORE going offline. They are not
  bundled. An administrator may be needed for that provisioning, but application
  installation uses a writable user directory and requires no root.
- Allow roughly 1 GB disk plus the Python environment/wheels, and preferably
  8 GB RAM as rehearsal headroom (not a measured minimum). Initial data loading
  takes tens of seconds on the development machine.

## What to transfer

A Git checkout alone is insufficient: the trusted model binary is Git-ignored.
The allowlisted `scripts/release.py bundle` command includes only:

- `backend/app/**/*.py`, runtime requirements and exact offline dependency lock;
- `frontend/src/` and built `frontend/dist/` assets;
- `data/v2/development.csv` (18,000 observations; existing label columns are
  separated at ingestion and never consumed by inference/graph construction);
- `artifacts/ml/tuning/run-001/tuned-42/{pipeline.joblib,manifest.json,threshold.json}`;
- install/start/verify scripts, wheelhouse builder, dashboard builder, release and
  runtime verifiers, this guide, demo walkthrough and rehearsal checklist;
- `release_manifest.json`, and Linux `wheels/*.whl` plus their manifest when ready.

The artifact manifest contains feature order, fitted preprocessing metadata,
versions and provenance; threshold.json is the frozen validation threshold.
No separate training config or report is needed for runtime. Training corpora,
sidecars, other model seeds, predictions, plots, tests, Git metadata, secrets,
virtual environments and browser caches are excluded by the allowlist. Keep the
full repository separately for regression tests and historical evidence.

## Online preparation

On the current trusted source machine, build assets, make the checksum inventory
and create a preparation bundle (using the existing Windows venv if applicable):

```powershell
.\venv\Scripts\python.exe -B scripts/build_dashboard.py
.\venv\Scripts\python.exe -B scripts/release.py manifest
.\venv\Scripts\python.exe -B scripts/release.py bundle --without-wheels
```

`releases/bitcoin-offline.tar.gz` is preparation-only until Linux wheels are added.
The command refuses to overwrite an existing archive; choose a fresh `--output`
filename for another build. Transfer it securely with its printed SHA-256.

On an internet-connected Linux preparation machine matching the target, with
CPython 3.13.14 and pip already installed:

```bash
tar -xzf bitcoin-offline.tar.gz
cd bitcoin-offline
python3 -B scripts/release.py verify
PYTHON=python3 bash scripts/build_wheelhouse.sh
python3 -B scripts/release.py bundle --output releases/bitcoin-offline-linux.tar.gz
```

The wheelhouse builder requires Linux, downloads binary wheels only with exact
pins, records wheel hashes/platform, then uses the offline installer and performs
real local inference/graph checks. If a pinned Linux wheel cannot be resolved,
STOP: preparation has not succeeded. Obtain those exact trusted wheels for this
environment; do not loosen versions or claim portability. A failed build leaves
`wheels/` for inspection; move it aside before a fresh build. No Linux wheels have
been produced or verified in the current Windows milestone.

Copy the final archive and its SHA-256 to the offline target. Run the checklist
with networking disabled before treating it as a verified Linux release.

## Completely offline installation

In a writable directory on the provisioned target:

```bash
sha256sum bitcoin-offline-linux.tar.gz
# Compare with the hash received through your trusted transfer channel.
tar -xzf bitcoin-offline-linux.tar.gz
cd bitcoin-offline
python3 -B scripts/release.py verify
PYTHON=python3 bash install.sh
```

The installer checks Python and all runtime/wheel hashes, creates `.venv`, installs
with `--no-index --find-links=... --only-binary=:all:` and checks dependency
consistency and inference. It never falls back to PyPI. It uses the exact
`backend/requirements-offline-lock.txt`, rather than the broad development
requirements. Missing/wrong-platform wheels fail visibly. Existing `.venv` is
reused only if its interpreter is compatible; move a broken environment aside.

Checksums detect damage, not authenticity. Trust the publisher and transfer
channel before loading joblib/pickle files, which can execute code. Do not replace
or regenerate manifests to hide an unexpected checksum failure.

## Start, stop and restart

```bash
bash start.sh
```

Open **http://127.0.0.1:8000**. Keep the terminal open. Wait for data/model loading
on the first investigation request. The launcher resolves its own directory,
rebuilds local dashboard assets, verifies the release and binds only to loopback.
Stop with **Ctrl+C**; restart with the same command. No daemon or persistent
server state needs cleanup. Port 8000 must be free.

Windows remains supported from the repository root:

```powershell
.\venv\Scripts\python.exe -B scripts/build_dashboard.py
.\venv\Scripts\python.exe -B -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

## Demo walkthrough

1. Wait for the dashboard to be ready. Open the first investigation queue entry:
   `6438536fd7ddeb015a2a0a7e5cc5f0d2df04d600d9ea0592c9fa3f1a41db3202`.
2. Inspect its graph, frozen score/threshold and separate network context.
3. Select/search connected address `1ESbdF6ACUgGWDe9fvPjeisQRNLWvzPJtE`.
   Expand its neighbourhood, try 1/2/3 hops and inspect its timeline.
4. Follow [the deterministic walkthrough](docs/demo_walkthrough.md) to trace
   the retained **30-transaction / 58-second** sequence. The 58 seconds is the
   observation time span, not application execution time. This sequence was
   evaluation-selected, not discovered by the model. Ground truth is not a model
   prediction. Address paths do not prove specific UTXO spends or wallet ownership.

## Verification and troubleshooting

```bash
bash verify.sh
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/overview
```

`verify.sh` does not need a running server. It checks hashes, pip consistency,
loads the trusted artifact/dataset and exercises ASGI dashboard/API routes while
Python socket connections and DNS are denied. This is process-level testing,
not OS network isolation or a browser test. Use the [release checklist](docs/release_checklist.md)
for actual disconnected-machine/browser rehearsal. The full repository can run
`python -B -m pytest -q -p no:cacheprovider` from `backend/` with dev dependencies;
those dependencies/tests are intentionally absent from the minimal runtime bundle.

- Python mismatch: provision exact CPython 3.13.14 and set `PYTHON=/path/to/python3.13`.
- Missing venv/ensurepip: provision them before disconnecting. Do not use sudo pip.
- No matching wheel: rebuild the wheelhouse on compatible Linux; never use Windows
  wheels. Inspect `wheels/manifest.json` for build platform and architecture.
- Checksum failure/missing artifact: recopy the trusted release, including the
  ignored model files. A source-only ZIP or Git clone is not a complete release.
- Investigation HTTP 503: read the server terminal; check artifact versions,
  dataset, memory and hashes. Initial loading is slow; allow it to finish.
- Port in use: stop the previous application with Ctrl+C before restarting.
- Unset `BTI_DATASET` and `BTI_ARTIFACT` for the bundled demo; verification refuses
  overrides. Advanced runtime overrides retain existing behavior and are outside
  this release's checksummed-default verification.
- Execute shell files with `bash` if a checkout does not preserve executable
  permissions. Archives set them executable; `.gitattributes` preserves LF.

## Audit and limitations

Runtime Python paths use pathlib and file-relative repository roots. The graph
and inference path needs no Git executable; Git subprocess use is limited to
training provenance. Frontend fetches are relative localhost API paths. The only
external-looking frontend URL is the W3C SVG namespace identifier; it performs no
request. FastAPI `/docs` and `/redoc` redirect to local OpenAPI JSON. Documentation
contains historical/reference URLs and Windows commands; they are not runtime
requirements. No external runtime service was found.

No production generation, retraining, threshold change or benchmark selection is
part of packaging. Synthetic performance remains limited, including poor layering
and peeling recall. Source compatibility audit is complete; exact Linux wheel
availability and execution remain pending. The runtime package must pass the
Linux/disconnected rehearsal before it can be advertised as Linux-verified.
