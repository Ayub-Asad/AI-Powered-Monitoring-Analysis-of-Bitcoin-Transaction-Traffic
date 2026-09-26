# Project instructions

Smart India Hackathon 2026, PS 26146: AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic.

- Read PROJECT_CONTEXT.md and README.md before changes. Actual code and executed tests are the source of truth; historical notes may be superseded.
- Preserve working ingestion, API contracts, legacy data and historical context. Make targeted changes and test them.
- Work on the requested branch. Do not commit, push or merge without explicit instruction.
- Completed milestone: offline transaction-only Isolation Forest anomaly detection. Next milestone: graph-based investigation of wallet relationships, transaction chains and temporal patterns, integrated with existing ML anomaly scores. Graph implementation requires a separate task; do not implement it during the ML documentation/commit handoff. Frontend remains outside scope.
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
