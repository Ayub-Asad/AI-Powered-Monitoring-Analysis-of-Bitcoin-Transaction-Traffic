# Investigation dashboard implemented - 2026-09-29

Current branch: `feat/investigation-dashboard`. The local offline investigation application is implemented. Next milestone: Linux offline prototype packaging. This section supersedes earlier milestone-status statements; historical sections remain below. No commit, push or merge performed.

- One FastAPI process serves the static production workspace and bounded `/api` health, overview, ranked alerts, transaction/address details, graph, timeline, search and chronological trace endpoints. Existing ingestion routes retain their contracts.
- `frontend/src/` uses local HTML/CSS/JavaScript and SVG; `scripts/build_dashboard.py` creates the ignored static build without Node or frontend dependencies. The navy/cyan/amber workspace includes queue pagination, exact/partial search, selectable graph nodes, zoom/pan/reset, bounded 1–3 hop expansion, ordered trace highlighting, details, timeline and separate network context.
- Lazy lock-protected loading reuses canonical ingestion, existing frozen tuned-42 inference and the existing graph JSON v1 contract. Default dataset is development.csv; no production generation, fitting, tuning or recalibration. All 248 inventoried protected files retain their hashes.
- Measured live overview: 18,000 transactions, 7,059 addresses, 60,836 relationships and 6,153 frozen-threshold flags; dataset/model identities and counts come from loaded data. Initial load measured 39.161s during concurrent verification; this is not a performance benchmark.
- Full regression: 255 passed + 75 subtests, zero failures/skips, one known Starlette/httpx warning, 221.67s. Focused API checks: 33 passed, 25.14s. Production asset build and pip check passed. An initial root-path defect was fixed before the passing rerun.
- Real headless Edge browser smoke exercised queue selection, multi-hop expansion, address inspection, timeline, search, chronological path highlighting and zoom/reset. No page JavaScript exceptions or external page requests. Evaluation-selected demonstration reconstructed 30 transactions within 58 seconds; this is not a model discovery or evidence of illicit activity.
- See `docs/dashboard.md`, `docs/demo_walkthrough.md` and `reports/dashboard/`. Browser profiles/screenshots are ignored in `artifacts/dashboard/`. Linux itself was not executed; package existing datasets/trusted artifacts and compatible dependencies, then verify on target Linux before claiming offline Linux readiness.

---

# Graph investigation implemented - 2026-09-28

Current branch: `feat/graph-investigation`. ML baseline and hyperparameter tuning remain complete and frozen. The offline graph backend is implemented; next milestone is API/dashboard integration and offline prototype packaging. The dashboard is not implemented. This section supersedes earlier next-milestone statements; all historical sections below are retained. No commit, push or merge performed.

- `backend/app/graph/`: deterministic bipartite address/transaction graph, exact repeated-allocation aggregation, nullable legacy values, descriptive address/component statistics, bounded lookups/neighbourhoods, chronological paths/sequences, timelines and filters.
- JSON contract `bitcoin-investigation-v1` includes score/threshold/flag/model identity, contextual network provenance, factual reasons, semantic styling and explicit truncation. Scores remain optional and unknown flags remain null.
- Frozen inference reuses the ordered ten-feature ML interface and trusted artifact loader. No production generation, fitting, tuning, recalibration or historical result changes. Graph/scenario metadata never enters ML features.
- Network observations remain contextual, not blockchain-native fields or ownership evidence. Address-linked paths do not prove particular UTXO spends, common ownership or criminality; equal timestamps do not establish ordering.
- Complete backend regression suite: 228 passed plus 75 passing subtests, zero failures/skips, one known Starlette/httpx warning, 128.93s. Focused graph suite: 29 passed, zero failures/skips, 1.59s. Existing tests may fit/generate isolated fixtures; no production experiments were run.
- Existing development graph: 18,000 transactions, 7,059 addresses, 25,059 total nodes, 60,836 directed relationships. Tuned seed-42 inference attaches scores to every transaction, with 6,153 frozen-threshold flags; this is a development smoke count, not a new accuracy result.
- Evaluation-only scenario verification reconstructs consecutive pairs for a 30-transaction layering and 24-transaction peeling example. Full layering and three-transaction previews are found; long peeling search reaches its configured state bound. That limit is disclosed, not interpreted as disconnection.
- Exact measured timings, protected-file verification and example IDs: `reports/graph/verification.json`. Test results: `reports/graph/tests.json`. Contract, limitations and reproduction: `docs/graph_investigation.md`. Generated graph exports/inventories are ignored under `artifacts/graph/`.
- No new HTTP routes or frontend. Future API work must manage graph lifecycle, pagination and request limits. Python implementation is offline and Linux-compatible; execution here used Windows, not a Linux runtime.

---

# Tuning milestone complete - 2026-09-28

The approved hyperparameter-tuning, validation false-positive analysis and one-shot final evaluation are complete on `feat/ml-tuning-fp-analysis`. No commit, push or merge has been performed or authorized. Graph investigation remains the next separate milestone. All prior baseline/history sections below are retained.

- Deterministic search: 12 configurations, seeds 42/43/44, exactly 36 production fits in 171.49s. Selected: 200 trees, max_samples 1024, max_features 0.8, bootstrap false. No ensemble.
- Primary validation objective: mean precision at exact top 1%; selected 28.52%, recall 1.90%, mean 51.33 true / 128.67 false alerts. Mean validation F1 0.319837. The 1% recall condition is feasibility only.
- Early temporary fixtures reused seed 404 (60 normal / 20 anomalous), potentially exposing its first 60 normal records. No fixture metrics drove selection. The user approved seed 405 instead; future generated fixtures use 9404 and amendment tests mock data without generating 405.
- configs/ml_final_405.json and seed_change.json record an additive amendment binding the unchanged original freeze. All fitted models, preprocessing, thresholds, ranking rules, selection and comparator policies stayed frozen. No production tuning/refitting was repeated.
- Fresh final: seed 405, exactly 18,000 records (15,300 normal / 2,700 anomalies), April 1 00:46:07 through April 14 11:21:47 UTC 2025; 7,003 wallets, 591 scoped generating actors, 16,555 scenarios. Generation 5.82s; total final workflow 20.63s; evaluated once.
- Identity audit: 21 reference populations, including original partitions, tracked v1/v2, 68 retained fixture files/four unique retained identity sets, known reconstructed fixtures and handwritten identities. Zero overlapping TXIDs, wallets, scoped actors/scenarios and raw scenarios where metadata exists. Required earlier-partition chronology passed. Three independent April fixture comparisons intentionally overlap calendar time; legacy grouping metadata is unavailable, not fabricated.
- Fresh-test mean top-1% precision: original IF 27.59% versus tuned 30.19%; recall 1.84% versus 2.01%; mean true alerts 49.67 versus 54.33 of 180. A modest improvement on this synthetic population, not operational adequacy.
- Mean frozen-threshold F1: 0.2871 original versus 0.2967 tuned; FPR 39.00% versus 34.63%; recall declines 53.80% to 51.62%. Heuristic F1 remains higher at 0.3347. Tuned seed-42 rapid-layering recall 11.11% and peeling recall 19.75% are worse than original 24.63%/26.91%; retained unchanged.
- Exact rankings and threshold flags are separate at 1%/2%/5%/10%. All seven models have precision/recall/F1/FPR/AP/PR-AUC/ROC-AUC, confusion matrices, category recall, alert counts and false alerts per 1,000 normal. Seed means/population SD are reported without selecting a best test seed.
- Validation-only false positives concentrate in tiny amounts and high fees. Global historical intensity uses [t-60s,t), excluding ties, and remains outside the unchanged 10-feature model contract. Hypotheses are not causal explanations.
- Full suite: 199 passed + 75 subtests, zero failures/skips, one known Starlette/httpx warning, 195.75s. Amendment checks: 17 passed in 6.34s. Earlier 182-test and focused-phase history is retained in reports. One interrupted test session had no recoverable completion result and was rerun rather than claimed passed. pip check and Git diff/hygiene checks passed.
- All 58 protected baseline/data files and 130 original tuning-frozen files retain their hashes. Generated corpora, models, identity inventories and scores are ignored. Overwrite and one-shot guards remain active.
- See docs/ml_tuning.md, docs/ml_false_positive_analysis.md, docs/ml_tuning_results.md and reports/ml/tuning/run-001/. Source and exact reproduction commands are documented. Shared generator mechanisms, limited scenario support and synthetic prevalence preclude real-world accuracy/ownership/criminality claims.

---

# Current milestone status - 2026-09-26

The offline transaction-only Isolation Forest milestone is complete and validated on `feat/ml-anomaly-detection`. Documentation handoff, commit and push of this branch are user-authorized after final verification; merging into main and branch deletion are not authorized. The earlier milestone/history below is retained; this section describes the current implementation.

Next milestone: graph-based investigation of wallet relationships, transaction chains and temporal patterns, integrated with existing ML anomaly scores. No graph analysis is implemented in this handoff. Preserve the frozen experiment, causal-time boundaries and the distinction between address relationships and verified ownership.

Final read-only audit: 160 passing tests and 75 passing subtests, zero failures/skips, one known Starlette/httpx warning, 52.90s. Full corpus regeneration and experiment model retraining were not rerun during that audit. Saved predictions and all reported evaluation metrics were independently verified against ground truth; regression tests exercised isolated temporary fixtures. This is separate from the earlier implementation timings below.

Handoff result: 10 numerical transaction features, independent training/validation/test corpora, training-only preprocessing and validation-only threshold calibration. Isolation Forest seed 42 achieved precision 18.79%, recall 55.22%, F1 0.2804 and false-positive rate 42.12% on the frozen synthetic test corpus. The heuristic baseline performed better. Rapid-layering recall (19.63%) and peeling recall (27.65%) remain weak. No real-world deployment accuracy claim is made.

- `backend/app/ml/` provides the strict ordered 10-feature boundary, training-only median imputation, fixed monetary/rate/ratio log transforms, Isolation Forest, robust-deviation heuristic, validation-F1 calibration, scoring, artifact persistence and offline CLI. Existing ingestion, feature extraction and FastAPI contracts are unchanged.
- Versioned experiment configuration: `configs/ml_baseline.json`. Model seeds 42/43/44; predefined reference 42; 300 trees, 256 samples/tree, no bootstrap/scaler, `contamination=auto`; application threshold is external and uses `score = -score_samples`, `flagged = score >= threshold`.
- Independent corpora generated by `scripts/prepare_ml_datasets.py`: train seed 101 (15,300 normal, no injected anomalies), validation seed 202 and test seed 303 (each 15,300 normal + 2,700 anomalous). Observation periods are nonoverlapping January/February/March 2025 windows. Feature matrices: 15,300 x 10; 18,000 x 10; 18,000 x 10.
- All corpus pairs have zero overlaps in TXIDs, wallet addresses, scoped actors/scenarios and raw scenario IDs. Whole scenarios remain in their corpus. Train/validation/test have 5,773/7,013/6,952 wallets and 15,300/16,555/16,555 scenarios. Train labels are never read or used to filter rows. Validation labels calibrate thresholds; test labels are read only after every artifact is frozen and scored.
- Reference test precision 0.187902, recall 0.552222, F1 0.280395, average precision 0.190786, trapezoidal PR-AUC 0.190485, ROC-AUC 0.591120, FPR 0.421176. Confusion: TN 8,856, FP 6,444, FN 1,209, TP 1,491. Across forest seeds, F1 mean 0.285832, population SD 0.005983. The heuristic is stronger here: F1 0.329059, ROC-AUC 0.620576; no test-informed replacement or tuning was performed.
- Reference category recall: rapid layering 19.63%, dust 98.02%, high-value 87.16%, peeling 27.65%, unusual ports 44.44%, fees 88.89%, geo 38.15%. High category recall accompanies high FPR and is not evidence of criminality or mechanism-specific detection.
- Fixed test budgets 1%/5%/10% mean 180/900/1,800 alerts; reference precision 27.78%/18.44%/20.89% (50/166/376 true positives). All seeds and heuristic results are retained.
- Full suite: **160 passed, 75 passing subtests, 0 failed, 0 skipped**, one existing Starlette/httpx warning, **63.16 seconds**. This preserves all 105 prior tests and adds 55 ML tests. Exact counts and focused-phase history: `reports/ml/validation.json`.
- Measured generation: 8.502/7.023/7.836s; forest fits 1.145/1.434/0.922s; training workflow 25.783s; full test evaluation with plotting 31.872s. Timings are observations, not benchmarks. Score CLI smoke: existing v2 development produced 18,000 x 6 rows, 7,870 flags, zero missing cells and unique TXIDs. This is a smoke result, not an additional held-out metric.
- Existing v1/v2 data are preserved. All development/regression manifest hashes match. The existing regression dataset is not an independent ML test set: its 1,000 TXIDs overlap development. Existing development records form one related component via actors/wallets/scenarios.
- Large `data/ml/` corpora and `artifacts/ml/` binaries/scores/plots are Git-ignored; compact manifests and results are in `reports/ml/`. Dependencies installed into the existing venv; exact environment is `backend/requirements-ml-lock.txt`. Trusted local artifacts require recorded Python/package versions and schema/checksum validation.
- See `docs/ml_anomaly_detection.md` for all reproduction commands, model contracts and causal-wallet design; `docs/ml_results.md` for all seed/category/budget results. No graph, frontend or causal wallet implementation was added. No deployment performance claim is made: labels are synthetic and operational prevalence/alert tolerance remain unknown.

---

# Previous milestone status - 2026-09-25

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
