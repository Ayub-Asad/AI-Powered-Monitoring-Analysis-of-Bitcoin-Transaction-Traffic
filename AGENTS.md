# Project instructions

Smart India Hackathon 2026, PS 26146: AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic.

- Read PROJECT_CONTEXT.md and README.md before changes. Actual code and executed tests are the source of truth; historical notes may be superseded.
- Preserve working ingestion, API contracts, legacy data and historical context. Make targeted changes and test them.
- Work on the requested branch. Do not commit, push or merge without explicit instruction.
- Completed milestones: offline transaction-only Isolation Forest anomaly detection, hyperparameter tuning, graph investigation and offline investigation API/dashboard. Offline Linux packaging is prepared; actual Linux verification is pending.
- Treat generated data as synthetic Bitcoin-like observations, not verified on-chain transactions, actual GeoIP results or evidence of wallet ownership.
- v2: amount_btc is the sum of all outputs including change; inputs equal outputs plus fees. Use integer satoshis for monetary accounting.
- Preserve legacy warning-only count validation. Enforce strict paired amount arrays, address/count lengths and conservation for v2.
- Keep label/anomaly_type and actor/scenario metadata out of canonical features. Feature extraction receives only IngestionResult.transactions.
- Never silently estimate legacy per-address flows. Keep identifiers and network context out of default numerical ML columns.
- Aggregate repeated address allocations but count each wallet once per transaction. Features must be deterministic and documented.
- Run the relevant tests after each phase and the complete suite before reporting completion. Report actual passes, skips, failures and measured timings.
- Update PROJECT_CONTEXT.md and relevant documentation after major work; retain historical sections.
- Use the existing venv and dependency files. Commands and artifacts are documented in README.md.
- ML uses the existing ordered 10-feature transaction allowlist. Never feed identifiers, context, truth, or whole-window wallet features into fitting.
- Keep corpus seeds 101/202/303 and model seeds 42/43/44 in versioned experiment configuration. Normal-only training is by generation, not label filtering.
- Verify disjoint corpus identities and chronological periods. Fit all preprocessing on training only; calibrate thresholds on validation only; freeze every artifact before opening test labels.
- Preserve frozen experiments; never select settings/seeds/budgets using test results. Report poor category results unchanged.
- Keep generated ML corpora, models and detailed plots ignored; retain compact manifests/evaluation reports and exact regeneration commands. Do not remove tracked v1/v2 datasets.

## Verified ML handoff

- Final read-only audit: 160 passing tests and 75 passing subtests, zero failures/skips, one known Starlette/httpx warning (52.90s).
- Baseline uses 10 numerical transaction features and independent training, validation and test corpora, with training-only preprocessing and validation-only threshold calibration.
- Frozen synthetic test results for Isolation Forest seed 42: precision 18.79%, recall 55.22%, F1 0.2804 and false-positive rate 42.12%. The heuristic baseline performed better. Rapid-layering recall (19.63%) and peeling recall (27.65%) remain weak.
- Full corpus regeneration and experiment model retraining were not rerun during the final read-only audit. Saved predictions and reported evaluation metrics were independently verified; regression tests used isolated temporary fixtures.
- These are synthetic-data findings, not real-world deployment accuracy claims or evidence of criminal activity. Preserve the frozen experiment when starting graph investigation.

## Verified tuning handoff - 2026-09-28

- Completed on `feat/ml-tuning-fp-analysis`: 12 configurations x seeds 42/43/44, 36 production fits. Selected 200 trees, 1,024 samples, max_features 0.8, bootstrap false. No ensemble. Primary objective is mean validation top-1% precision; the 1% recall condition is a feasibility check only.
- Final seed changed from 404 to 405 with explicit user approval after earlier small fixtures reused 404. configs/ml_final_405.json and seed_change.json record the amendment. Models, preprocessing, thresholds, selection, ranking and comparison policies stayed frozen; no production refit or retuning occurred. Future fixtures must not generate reserved final seeds; generated regression fixtures use 9404.
- Seed-405 final evaluation ran once: 15,300 normal + 2,700 anomalous records in April 2025. All 21 known reference-population identity audits passed before scoring; required chronology passed. Independent April regression windows overlap intentionally and are disclosed; missing legacy grouping identities are not fabricated.
- Fresh-test mean top-1% precision is 30.19% tuned versus 27.59% original IF, with recall 2.01% versus 1.84%. Mean F1 improves 0.2871 to 0.2967, but threshold recall declines 53.80% to 51.62%. Heuristic F1 is higher at 0.3347. Tuned seed-42 rapid-layering/peeling recall is only 11.11%/19.75%; preserve these poor results.
- Complete suite: 199 passed + 75 subtests in 195.75s, zero failures/skips, one known Starlette/httpx warning; pip check passes. All 58 protected baseline/data files and 130 original tuning-frozen files are unchanged. See docs/ml_tuning_results.md and reports/ml/tuning/run-001/.
- Seed 405 is now a published benchmark, not an untouched test for future model selection. Preserve both freezes and the one-shot/overwrite guards. Never use final results to choose settings, seeds or budgets, or remove difficult examples.
- Historical global activity diagnostics use [t-60s,t), exclude tied timestamps and remain outside the 10-feature model contract. Graph relationships and causal temporal investigation remain the next separate milestone. No commit, push or merge without explicit instruction.

## Graph investigation handoff - 2026-09-28

- `backend/app/graph/` consumes canonical transactions and optional frozen scores; no graph ML or changes to ingestion/features/ML freezes.
- Preserve bipartite address -> transaction -> address semantics. Never infer specific input/output attribution, ownership or verified UTXO spends. Address-linked chronological paths require strictly increasing transaction times; ties are not ordered.
- Aggregate repeated allocations in integer satoshis; count each address/transaction once in transaction counts. Preserve null legacy allocations and source count mismatches.
- Graph construction/traversal must never consume evaluation labels, categories or actor/scenario metadata. Only verification scripts/tests may use sidecars to select evaluation examples.
- Keep node/edge/search limits, deterministic JSON v1, unknown score state, provenance and truncation visible to dashboard consumers. Network fields are reported/synthetic transaction context, not ownership evidence.
- See `docs/graph_investigation.md` and `reports/graph/` for exact commands and measured verification. Next: API/dashboard integration and offline prototype packaging. No commit, push or merge without explicit instruction.

## Dashboard handoff - 2026-09-29

- `backend/app/investigation.py` wraps the existing canonical graph and frozen inference with bounded read-only `/api` routes. Existing `/health` and `/ingest` contracts are preserved; uploads do not replace the investigation dataset.
- `frontend/src/` is dependency-free HTML/CSS/JavaScript with a local SVG renderer. Run `scripts/build_dashboard.py` before serving; ignored `frontend/dist/` is the production build. No Node/CDN/cloud runtime dependency.
- Keep score ranking in alerts `items` separate from deterministic graph `nodes` ordering. Preserve null score states, factual reasons, truncation, synthetic context and strict chronological trace semantics. Do not introduce new risk thresholds or ownership claims.
- Complete suite: 255 passed + 75 subtests in 221.67s, no failures/skips, one known Starlette/httpx warning. Focused API suite: 33 passed in 25.14s. Production build, real Edge browser investigation smoke and pip check passed; 248 protected hashes unchanged.
- Documentation: `docs/dashboard.md`, `docs/demo_walkthrough.md`; compact verification: `reports/dashboard/`. Demo sequence is evaluation-selected, not a model discovery. No production generation, retraining or retuning occurred.
- Windows runtime verified. Linux wheels, trusted artifact compatibility, packaging and Linux execution remain the next milestone. No commit, push or merge without explicit instruction.

## Offline release handoff - 2026-09-29

- Packaging prepared on `feat/offline-linux-release`; Linux execution remains PENDING. Use README_OFFLINE.md and docs/release_checklist.md. Do not claim Linux wheels, clean-machine installation or OS network isolation passed until actually run.
- Frozen trusted artifact requires exact CPython 3.13.14 and pinned scientific versions. Preserve the compatibility guard and backend/requirements-offline-lock.txt; no retraining or artifact rewriting for portability.
- scripts/release.py packages an explicit runtime allowlist, including the ignored tuned-42 model. A Git clone is not a complete release. Build matching Linux wheels with scripts/build_wheelhouse.sh before producing an offline-installable bundle.
- install.sh uses only local binary wheels; start.sh binds 127.0.0.1:8000. Shell files use LF and can be invoked with bash; archives assign executable permissions.
- Regression: 265 passed + 75 subtests, zero failures/skips, known warning, 176.96s. Focused release tests: 10 passed in 6.95s. Socket-denied runtime checks passed in 73.690s; this is Python process-level testing, not OS isolation. All 248 protected files unchanged.
- Final remaining task is Linux/disconnected rehearsal, not feature development. Keep historical results and limitations. No commit, push or merge without explicit instruction.
- Relocated minimal-bundle inference passed with Python networking denied (45.082s). Edge page smoke passed at three viewport sizes with zero external page requests/exceptions; Windows process stop/restart HTTP check passed. Dashboard asset-manifest output uses explicit LF to preserve cross-platform checksums.
