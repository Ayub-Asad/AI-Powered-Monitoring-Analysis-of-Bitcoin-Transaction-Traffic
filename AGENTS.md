# Project instructions

Smart India Hackathon 2026, PS 26146: AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic.

- Read PROJECT_CONTEXT.md and README.md before changes. Actual code and executed tests are the source of truth; historical notes may be superseded.
- Preserve working ingestion, API contracts, legacy data and historical context. Make targeted changes and test them.
- Work on the requested branch. Do not commit, push or merge without explicit instruction.
- Current milestone: Dataset v2 and feature engineering. ML training, graph analysis and frontend are outside this milestone.
- Treat generated data as synthetic Bitcoin-like observations, not verified on-chain transactions, actual GeoIP results or evidence of wallet ownership.
- v2: amount_btc is the sum of all outputs including change; inputs equal outputs plus fees. Use integer satoshis for monetary accounting.
- Preserve legacy warning-only count validation. Enforce strict paired amount arrays, address/count lengths and conservation for v2.
- Keep label/anomaly_type and actor/scenario metadata out of canonical features. Feature extraction receives only IngestionResult.transactions.
- Never silently estimate legacy per-address flows. Keep identifiers and network context out of default numerical ML columns.
- Aggregate repeated address allocations but count each wallet once per transaction. Features must be deterministic and documented.
- Run the relevant tests after each phase and the complete suite before reporting completion. Report actual passes, skips, failures and measured timings.
- Update PROJECT_CONTEXT.md and relevant documentation after major work; retain historical sections.
- Use the existing venv and dependency files. Commands and artifacts are documented in README.md.
