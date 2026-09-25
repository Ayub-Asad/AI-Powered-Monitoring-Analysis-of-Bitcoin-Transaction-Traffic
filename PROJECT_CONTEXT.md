# Current milestone status - 2026-09-25

Dataset v2 + Feature Engineering is implemented and validated on `feat/dataset-v2-feature-engineering`. The historical notes below are retained; where they conflict with this section, this section and the actual code supersede them.

- Baseline: 69 passed, 7 skipped (obsolete generator-test path), 0 failed. Supplemental in-memory path correction: all 7 passed.
- Final: 105 passed, 0 skipped, 0 failed, 75 passing subtests, one Starlette/httpx deprecation warning; measured 59.96 seconds.
- Fixed generator test discovery, negative sub-satoshi fee acceptance (including underflow), and timestamp OverflowError escapes.
- V2: exactly 18,000 records at seed 42: 15,300 normal + 2,700 anomalies. Distribution: rapid 540; dust, high-value, peeling and ports 405 each; fees and geo 270 each. Complete scenarios, integer-satoshi conservation, persistent actors and synthetic observer mappings.
- Regression dataset: 1,000 records (850/150). Original v1 CSV remains unchanged and reproducible with --schema-version 1.
- V2 amount_btc is sum of outputs INCLUDING CHANGE; inputs equal outputs plus fee. Both amount arrays required together; v1 fields/values and warning-only count policy remain compatible.
- Canonical output is now 19 columns (two optional allocation lists added). Ground truth remains separate. CSV JSON-array cells and native JSON/JSONL arrays are supported; old pipe lists still work.
- Features implemented in backend/app/features/: transaction table 18,000 x 11; wallet table 7,059 x 21; 10 and 17 default behavioural ML columns respectively. Separate context tables; explicit identifiers and availability flags. No silent legacy allocation estimates.
- 7,059 unique wallets, 280 observed IPs; zero duplicate TXIDs, rejections, conservation failures, missing development feature values or selected-ML infinities. 4,253 repeated-address warning instances are preserved and handled correctly.
- Full CSV/JSONL equivalence, seed determinism, input-order-independent features, and full-dataset health/upload API checks pass using FastAPI TestClient. No live listening-server test is claimed.
- Latest measured stages: generation 7.91s, CSV ingestion 10.65s, feature extraction 5.42s; measurements under concurrent test load, not benchmarks.
- Numerical/contextual quality diagnostics are saved; overlapping marginal distributions do not eliminate multivariate shortcuts. Data is synthetic, not calibrated to real traffic, no full UTXO ledger or GeoIP/ownership claims.
- Whole-window wallet features are descriptive, not causal online features. Legacy exact flows may be unavailable. Coinbase/addressless outputs/XML remain unsupported.
- AGENTS.md is populated; README.md and docs/dataset_v2.md, docs/features.md, docs/milestone_validation.md define commands, contracts, limitations and results. Machine-readable reports are in data/v2/.
- No model training, graph analysis or frontend was implemented. Validation completed before the subsequent user-authorized commit/push; no merge was requested.

Commands from repository root (PowerShell):

```powershell
.\venv\Scripts\python.exe -B scripts\validate_pipeline.py
.\venv\Scripts\python.exe -B scripts\btc_synthetic_dataset_generator.py --schema-version 2 --seed 42 --both --out data/v2/development.csv
.\venv\Scripts\python.exe -B scripts\btc_synthetic_dataset_generator.py --schema-version 2 --seed 42 --n-normal 850 --n-anomalous 150 --both --out data/v2/regression.csv
Push-Location backend
..\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
..\venv\Scripts\python.exe -B -m app.features ../data/v2/development.csv --out-dir ../data/v2 --burst-window-seconds 60
Pop-Location
```

Next milestone: Isolation Forest anomaly detection and leakage-safe evaluation, with train-only preprocessing, deliberate missingness handling, and time/scenario/actor separation. Define any wallet evaluation target separately; feature extraction must never read ground truth.

---

# Historical context (retained; superseded where noted above)

# Bitcoin Transaction Analysis — Project Context

## Problem Statement
Build a system for Bitcoin transaction analysis that can ingest transaction
data, construct transaction/address relationships, engineer useful features,
detect/analyze suspicious activity, expose results through an API, and
visualize the results through a dashboard.

## Current Architecture

Dataset
   ↓
Ingestion
   ↓
Data Cleaning / Normalization
   ↓
Feature Engineering
   ↓
ML / Anomaly Detection
   ↓
Graph Analysis
   ↓
FastAPI
   ↓
Dashboard

## Current Dataset

Dataset version: v1

Current data:
- Synthetic Bitcoin transaction dataset
- Generated for development/testing
- Contains transaction-level information
- Used to test ingestion and downstream pipeline

Important:
Do not redesign the dataset schema without discussing it first.

## Dataset Schema

in the dataset file

## Completed

- Problem statement understood
- Initial architecture decided
- Synthetic dataset v1 generated
- Dataset reviewed for initial development
- Development pipeline defined
- **Ingestion layer (v1)**: CSV/JSON/JSONL readers, validation, normalisation,
  duplicate detection, canonical schema, `POST /ingest`, `GET /health`, CLI,
  76 unit tests (see "Ingestion Layer" below)
- **Ingestion milestone review (2026-09-25)**: full suite re-run, real dataset
  re-verified end-to-end, canonical schema checked for feature-engineering
  readiness, and 3 of the 4 known generator data-quality issues fixed at the
  source (see "Generator Data-Quality Fixes" below). STATUS: READY.

## Not Completed

- Real-data ingestion adaptations (coinbase / OP_RETURN txs, XML reader)
- Feature engineering
- ML/anomaly detection
- Graph construction
- API integration
- Dashboard
- Explainability
- Final polish

## Tech Stack

- Python
- Pandas
- NetworkX
- Scikit-learn
- FastAPI
- React
- Tailwind CSS
- [Other technologies actually being used]

## Design Decisions

- Use modular pipeline architecture
- Keep ingestion separate from feature engineering
- Keep ML separate from graph analysis
- API acts as bridge between backend analysis and dashboard
- Do not unnecessarily rewrite completed components
- Ingestion never uses `label`/`anomaly_type`: they are split into a separate
  `ground_truth` frame (evaluation only) and are absent from the canonical
  transaction table by construction
- Format support is a plug-in registry (`register_reader`); adding XML = one
  `BaseReader` subclass, no pipeline/validator/API changes
- Bad data is reported, never raised: `ingest_bytes` returns an
  `IngestionReport`; only bugs raise

## Known Issues

- Dataset is synthetic
- Real Bitcoin data integration is pending
- Some assumptions in synthetic data may need validation
- Dataset schema should remain stable unless a concrete requirement requires modification
- **Generator inconsistencies found during ingestion, 3 of 4 fixed 2026-09-25 (see below).
  Not fixed / by design:**
  - 210 duplicate timestamps at 1 s resolution (ordering ties broken by file order) — harmless,
    `pipeline.py` breaks ties deterministically by `source_row`
  - `country`/`asn` are chosen independently of the actual `src_ip` (not a GeoIP lookup) —
    this is an intentional simplification the generator's own docstring already disclosed, and
    fixing it would need a real IP-to-ASN allocation table, which is a generator redesign, not a
    bug fix. Left as-is per "do not redesign the entire generator." A misleading doc comment
    that overclaimed `country`/`asn` were derived from `src_ip` was corrected.
  - `country`/`asn` correlate with anomaly type via each generator's `high_risk_bias` parameter,
    so a naive model could use `country` as a near-perfect anomaly predictor. This is the
    "trivially separable" issue already noted below under Known Issues and is explicitly
    deferred to the planned generator rework, not something to patch now.
- Duplicate policy (first txid wins) is right for this dataset. In real
  network-capture data the same txid may legitimately be observed from many
  peers; revisit then (first-seen timestamp would matter).
- Address validation is structural (no checksum) because synthetic addresses
  have no valid checksums. Coinbase txs (no input address) and OP_RETURN
  outputs (no address) are currently rejected as EMPTY_ADDRESS_LIST.
- Naming: `Claude.md` says `PROJECT_CONTEXT.md` but the file is `project_context.md`
  (case matters on Linux). Pick one.

## Generator Data-Quality Fixes (2026-09-25)

Three of the four issues from the milestone review were root-caused to specific
generator bugs and fixed with small, targeted edits to
`btc_synthetic_dataset_generator.py` (no schema change, no redesign):

1. **num_inputs/num_outputs vs address-list length** — was 206/8,764 rows
   mismatched. Root cause: `gen_high_value_single_hop` drew the input count
   twice independently (once for the address list, once for `num_inputs`);
   `gen_anomalous_port` hardcoded `num_inputs=1, num_outputs=1` regardless of
   how many addresses were actually sampled. Fixed by drawing the count once
   and reusing it for both the list and the field. **Verified: 0 mismatches
   across the regenerated dataset** (was blocking any graph-degree feature
   that trusted `num_inputs`/`num_outputs` over the address lists).

2. **Repeated output address in peeling_chain** — every peeling_chain
   transaction emitted the *same* address twice as `"addr|addr"` instead of a
   distinct peel-target and change address. Fixed to mint two distinct
   addresses; the chain now continues via the change address, as a real
   peeling chain does. **Verified: 0 duplicate-output rows in peeling_chain**
   (was going to create degenerate self-loop-like edges in the transaction
   graph for every single peeling_chain row, ~100+ rows).

3. **fee_rate_sat_vb vs fee_btc consistency** — in every anomaly generator
   except `fee_anomaly`, `fee_rate_sat_vb` was drawn independently of
   `fee_btc`, so implied transaction size (`fee_btc*1e8/fee_rate_sat_vb`)
   ranged from 11 to 36,000 vB — physically impossible, and a trivial
   shortcut a model could use to separate anomalous from normal rows for
   reasons that have nothing to do with genuine anomalous behaviour. Fixed by
   deriving `fee_rate_sat_vb` from `fee_btc` and an estimated vsize (same
   `140 + 40*n_in + 30*n_out` formula already used for normal traffic) in
   `rapid_fire_layering`, `dust_attack`, `high_value_single_hop`,
   `peeling_chain`, `anomalous_port_usage` and `geo_velocity`. The intended
   anomaly signal for each type is preserved (e.g. `high_value_single_hop`
   still pays a tiny absolute fee on a huge amount; only the sat/vB figure is
   now physically plausible, ~30-240 instead of an unrelated 1-4). **Verified:
   implied vsize is now 200-330 vB for every anomaly type** (was leaking a
   free "is this row internally consistent" feature).

**Not fixed:** `country`/`asn` not being geo-consistent with `src_ip` (see
Known Issues) — that requires a real IP-allocation table, which is a
generator redesign, out of scope for a bug-fix pass.

**Consequence of the fixes:** the generator consumes a slightly different
number of random draws per anomaly row, so `--seed 42` no longer reproduces
the exact byte-for-byte v1 file from before 2026-09-25 (record count moved
from 8,764 to 8,726 at the default budgets). It is still fully deterministic
for a given seed post-fix. The schema and column set are unchanged. Anyone
holding the old `btc_synthetic_dataset.csv` should regenerate it.

## Ingestion Layer (completed)

Location: `backend/app/ingestion/` (+ `backend/app/service.py`, `backend/app/main.py`)

    readers.py        format plug-ins (CSV, JSON, JSONL) + registry; parse only
    schema.py         canonical fields, required/optional, header aliases, ground-truth names
    validators.py     pure field normalisers (txid, ip, port, timestamp, BTC, addresses, ...)
    row_validator.py  raw record -> canonical record | list of errors (+warnings, +ground truth)
    pipeline.py       decode -> read -> resolve columns -> validate -> dedupe -> DataFrames
    report.py         IngestionReport (this is the /ingest response body)
    errors.py         stable error/warning codes
    service.py        (filename, bytes) -> (http_status, body); no framework dependency
    main.py           FastAPI wiring only (GET /health, POST /ingest)

Downstream interface:

    from app.ingestion import ingest_file
    result = ingest_file("dataset.csv")
    result.transactions   # canonical DataFrame: chronological, unique txid, NO label/anomaly_type
    result.ground_truth   # (txid, label, anomaly_type), row-aligned; evaluation only; None if absent
    result.report         # counts, errors, warnings, schema info

Canonical `transactions` columns (dataset v1 order, ground truth removed, plus lineage):
`timestamp`(UTC) `src_ip` `dst_ip` `src_port` `dst_port` `txid` `input_addresses`(list)
`output_addresses`(list) `num_inputs` `num_outputs` `amount_btc` `fee_btc`
`fee_rate_sat_vb` `country` `asn`(Int64) `asn_org` `source_row`(lineage, not a feature)

Policies:
- Required (row rejected if missing/invalid): timestamp, src_ip, dst_ip, src_port,
  dst_port, txid, input_addresses, output_addresses, amount_btc (>0), fee_btc (>=0)
- Optional (bad value -> null + warning, row kept): num_inputs/outputs (derived from
  lists if absent), fee_rate_sat_vb, country, asn, asn_org, label, anomaly_type
- Warnings (row kept): COUNT_MISMATCH, DUPLICATE_ADDRESS_IN_LIST, NON_PUBLIC_IP,
  NAIVE_TIMESTAMP_ASSUMED_UTC, INVALID_OPTIONAL_VALUE
- Duplicates: same txid -> first kept; reported as exact vs conflicting
- Invariant: rows_received = valid + rejected + duplicates
- HTTP: 200 (some valid rows) / 413 / 415 / 422 (nothing usable); body shape is identical
- Row numbers in reports = 1-based record number (header/blank lines not counted)

Run (from `backend/`):

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt
    python -m unittest discover -v            # or: pytest  (76 tests)
    python -m app.ingestion ../dataset.csv    # CLI summary (add --json for full report)
    uvicorn app.main:app --reload             # http://127.0.0.1:8000/docs
    curl http://127.0.0.1:8000/health
    curl -F "file=@../dataset.csv" http://127.0.0.1:8000/ingest

## Ingestion Milestone Review (2026-09-25)

| Check | Result |
|---|---|
| 1. FastAPI app can start | **Not verified in this sandbox** — no network access to install `fastapi`/`uvicorn`/`httpx`. `main.py` compiles cleanly (`python -m py_compile`) and contains only two routes, both thin wrappers around `service.process_upload`, which IS fully tested. Run `uvicorn app.main:app --reload` locally to confirm the boot; this is the one open item. |
| 2. `GET /health` | Not runnable here for the same reason; the handler is 3 lines returning a static dict plus `supported_formats()` — no failure mode besides the app not starting. `tests/test_api.py::test_health` covers it and will run wherever fastapi is installed. |
| 3. `POST /ingest` with real CSV | **Verified via `process_upload` (the exact function `/ingest` calls)**: `btc_synthetic_dataset_generator.py --seed 42` → 8,726 rows → HTTP 200, `status=success`, 8,726 valid, 0 rejected, 0 duplicate. |
| 4. `POST /ingest` with JSONL | **Verified**: same file regenerated as `.jsonl` produces an identical canonical DataFrame to the CSV version. |
| 5. Returned statistics correct | **Verified**: `rows_received == valid + rejected + duplicate` holds; spot-checked warning counts, duplicate detection (exact vs conflicting), and error codes against hand-built dirty fixtures in `tests/test_service.py` and `tests/test_ingestion.py`. |
| 6. All existing tests pass | **Verified**: 76 passed, 5 skipped (the `test_api.py` HTTP tests, auto-skipped because fastapi isn't installed in this sandbox — not a failure, a gap in this environment only). |
| 7. Canonical schema fit for feature engineering | **Verified suitable**: 16 typed columns + `source_row` lineage column, zero nulls on this dataset, `txid` unique, address lists never empty, chronologically sorted, `label`/`anomaly_type` structurally absent from the table. One residual gap for *future* real-world data: a coinbase tx (no input) or `OP_RETURN` output (no address) would currently be rejected as `EMPTY_ADDRESS_LIST` — not a problem for this synthetic dataset, but flag before ingesting real chain data. |

INGESTION STATUS: **READY**

Remaining open item (does not block feature engineering, but should be closed
before the API is demoed live): boot-test `uvicorn app.main:app` and the two
routes on a machine with network access, using the commands above. Everything
the route handlers do has been exercised through `process_upload` directly.

## Current Task

Feature engineering (not started). Consume `IngestionResult.transactions`.
Do NOT read `ground_truth` in feature code. Generator rework (input_amounts[] /
output_amounts[], less separable anomalies) is still pending and may require
updating `schema.py` (add optional list fields) and the address/amount
validators — the fixes above did not touch that separability question, only
the four specific data-quality bugs that would have broken feature/graph code.
