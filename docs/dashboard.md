# Offline investigation dashboard

Implemented on `feat/investigation-dashboard`. The next milestone is offline
Linux packaging. No Linux execution has been verified in this milestone.

## Start and build

From the repository root in PowerShell, using the existing environment:

```powershell
.\venv\Scripts\python.exe -B scripts/build_dashboard.py
.\venv\Scripts\python.exe -B -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The first investigation request loads the dataset,
performs frozen inference, and builds one in-memory graph. The page displays a
loading message during this work. Use one server worker for this prototype.
Stop with Ctrl+C. Rebuild after frontend edits and reload the browser.

The default inputs are `data/v2/development.csv` and
`artifacts/ml/tuning/run-001/tuned-42`. Optional environment variables:
`BTI_DATASET` (local CSV/JSONL path) and `BTI_ARTIFACT` (trusted local frozen
artifact directory). `BTI_ARTIFACT=none` explicitly starts without scores; turn
off **Flagged only** to browse unscored observations. Missing or invalid artifacts
produce HTTP 503 with a visible error, never silent fallback or retraining.
Paths default relative to the repository, independent of the working directory.
Uploads retain their existing report-only behavior and do not replace this graph.

## Architecture

FastAPI serves a dependency-free static HTML/CSS/JavaScript workspace. A Python
build script copies the three production assets and writes their SHA-256 manifest
to ignored `frontend/dist/`. There is no npm install, transpiler, CDN, remote font,
analytics, GeoIP lookup, graph database, or external application service.

`backend/app/investigation.py` owns a lock-protected lazy graph lifecycle and
read-only API. It consumes only `IngestionResult.transactions`, invokes existing
frozen inference, and uses existing graph operations and JSON v1 serialization.
It neither reads scenario sidecars nor changes graph or ML contracts. Model IDs
include the frozen artifact manifest hash. Overview counts are calculated from
the loaded graph; the dataset is identified by filename and SHA-256.

## Endpoints

Existing `GET /health` and `POST /ingest` are preserved. New GET routes:

`/docs` and `/redoc` redirect to the local `/openapi.json` contract, avoiding
FastAPI's default CDN-dependent documentation shells. Human-readable endpoint
documentation is provided here.

| Route | Response / bounds |
|---|---|
| `/api/health` | Process health and graph load state; does not force loading |
| `/api/overview` | Counts, score coverage, model IDs, dataset hash, load timing |
| `/api/alerts` | Score-descending `items`, deterministic ID ties; unknown scores last; offset and limit 1–100 |
| `/api/transactions/{txid}` | JSON v1 one-hop view including full selected transaction attributes |
| `/api/addresses/{address}` | JSON v1 one-hop view including address window statistics |
| `/api/graph/{entity}` | JSON v1; hops 1–3, max_nodes 1–250, max_edges 1–500 |
| `/api/timeline/{entity}` | Same bounds, ordered `timeline`; default two hops |
| `/api/search?q=...` | Exact match preferred, then partial lookup; 2–150 characters, limit 1–50 |
| `/api/trace?source=...&target=...` | Strictly chronological directed sequence; max_hops 1–100; 2,000 states / 4,000 edges / 10,000 inspections |

Entities accept raw TXID/address or graph namespaced IDs. Missing entities return
404, invalid filters/bounds return 422, loading failures return 503. Alerts,
graph and timeline support `flagged_only`, `min_score`, `min_amount_satoshis`,
and timezone-aware inclusive `start`/`end`. Alert pagination is separate from
graph serialization order: clients must use `items` for score ranking.

## Workspace and interactions

Four compact overview cards precede a ranked queue and central graph. Clicking
a queue row loads its neighbourhood, details and backend timeline. The default
view is one hop, capped at 80 nodes / 160 edges. Select 2 or 3 hops deliberately;
transaction → address → transaction spans two graph edges.

The local SVG renderer consumes graph JSON nodes and edges directly. It uses a
deterministic bounded force layout for neighbourhoods and ordered rows for paths.
Scroll or +/- zooms; drag the background to pan; Recenter resets the camera.
Click or keyboard-select a node to inspect it without discarding the current
graph. **Expand selected** recenters the investigation on that node. Native
tooltips expose identifiers, transaction time/amount/score or address counts;
edge tooltips expose known allocation amounts. Large views suppress most labels.

**Set selected as trace start**, select/search a destination, then **Trace to
selected** highlights the backend's ordered directed path. The timeline displays
sequence times, amounts and scores. No path within bounds is not proof of
disconnection. Truncation is shown in graph and timeline independently.

The dark navy/slate palette uses cyan diamonds for scored unflagged transactions,
amber diamonds for flags, gray for unknown scores, slate circles for addresses,
white selection outlines and bright cyan path edges. No extra red risk tier is
invented: the frozen model supplies one validated threshold, not risk classes.

Search handles exact matches, partial ambiguity, invalid input and no matches.
All data is inserted as text, not HTML. Request revision guards prevent older
investigations from replacing newer selections. Details separate synthetic
blockchain-style fields from network observations; null values stay unavailable.
Reasons are factual counts and frozen-threshold comparisons, not feature
attributions or accusations. Scores are not probabilities of crime. Address
totals are window allocations, not balances or inferred ownership.

## Verification and limitations

```powershell
.\venv\Scripts\python.exe -B scripts/build_dashboard.py
Push-Location backend
..\venv\Scripts\python.exe -B -m pytest tests/test_investigation_api.py tests/test_api.py -q -p no:cacheprovider
..\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
Pop-Location
# With the local API running:
.\venv\Scripts\python.exe -B scripts/smoke_dashboard.py
```

Optional real-browser verification uses an installed Chromium/Edge with a local
DevTools port and `scripts/smoke_dashboard.py --browser-port 9223`; the script
requires no browser automation package. It checks queue selection, expansion,
address details, timeline, exact search, path highlighting, zoom/reset, JavaScript
exceptions and page requests. Screenshots/profile output stay ignored in
`artifacts/dashboard/`. The smoke script uses the development corpus, existing
graph audit inventory, and evaluation-selected demo IDs, not arbitrary datasets.
Measured results are in `reports/dashboard/verification.json` and `tests.json`.

The Windows verification used a dedicated ignored browser profile and headless
Edge. The restricted test environment required `--no-sandbox --in-process-gpu
--disable-gpu --disable-software-rasterizer` to avoid a graphics-process crash;
these are test-harness options, not required application startup settings. The
DevTools port was 9223 and `--remote-allow-origins=*` was used only for the local
test connection. The smoke covered 1366×768, 1920×1080 and 768×900 layouts,
pan/zoom/reset and visible invalid/no-result/request-failure states. It blocked
HTTPS page requests and observed no external page requests; it did not disconnect
the host operating system from the network.

The UI is designed for laptop/projector widths, with vertical scrolling for
details. It is a single-process in-memory offline prototype: no authentication,
live ingestion, persistent cases, address clustering, or verified UTXO tracking.
The full graph is never sent on initial load. Dense regions intentionally return
partial views. The model's poor layering/peeling recall remains unchanged.

Before Linux packaging, include the existing trusted frozen artifact and dataset,
bundle compatible Python wheels, build the static assets, and test artifact
environment validation and browser startup on the target Linux machine. Existing
Windows measurements are not Linux verification. See [demo walkthrough](demo_walkthrough.md).
