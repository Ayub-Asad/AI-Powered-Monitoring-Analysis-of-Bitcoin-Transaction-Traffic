# Isolation Forest tuning protocol

This is a separate synthetic-data experiment. The frozen baseline configuration, models, predictions and reports remain unchanged. The original validation population has already calibrated baseline thresholds and is reused as development data. The original March test population is a historical benchmark, not an untouched final test.

## Preregistered decisions

`configs/ml_tuning.json` records all choices before fresh final data are generated. The Cartesian grid has 72 combinations: 100/200/300/500 trees, 256/512/1024 samples, 0.6/0.8/1.0 feature fractions, and bootstrap false/true. Canonical JSON ordering followed by Python `random.Random(26146).sample` selects 12 unique eligible configurations. Each fits seeds 42/43/44, exactly 36 forest fits; samples larger than the training population are excluded. All three seeds have equal weight. No ensemble is fitted.

Primary selection maximizes mean validation precision among the exact top 1% of records. Mean recall must be at least 1%; this is only a feasibility check, not adequate detection. Ties prefer greater mean validation F1 at each seed's validation-F1 threshold, then ascending canonical configuration JSON. No feasible candidate means stop without final evaluation. No test result can change these rules. With 15% anomaly prevalence, the maximum possible recall at a 1% budget is only 6.67%.

Training reuses normal-only-by-generation seed 101. Only the existing ordered 10 transaction features enter fitting. Median imputation is learned on training; fixed transformations and feature definitions remain unchanged. Validation seed 202 alone selects configurations and thresholds. No refit follows selection: selected candidate artifacts are copied, preserving fitted models. Frozen baseline seeds 42/43/44 and the heuristic are copied for comparison with their original F1 thresholds.

Final data are fixed at seed 405, April 1 2025 UTC start, 15,300 normal and 2,700 injected anomalous records. The user approved replacing 404 after early regression fixtures reused its normal-record prefix. The original seed-404 configuration and freeze are retained as historical provenance; `configs/ml_final_405.json` is the additive final-test amendment. The final command first verifies the freeze, artifacts, report hashes, environment and source hashes. An exclusive reservation prevents automatic retry, including after interruption. Only then does generation occur. The manifest and chronological/identity audit precede scoring; all seven models score before evaluation reads the label sidecar. Generation necessarily serializes labels but never selects a model. One final evaluation reports every selected seed without choosing a best test seed.

## Alerts and metrics

Scores are `-score_samples`; larger is more anomalous. Exact budgets use `ceil(N * budget)` at 1%, 2%, 5% and 10%, sorted by descending score and ascending TXID. They may split tied scores. Every budget reports precision, recall, F1, true/false alerts, confusion matrix, FPR and false alerts per 1,000 normal transactions.

Threshold alerts use `score >= cutoff`, including every tie. Each model has its validation-F1 threshold plus validation score cutoffs at the four budgets. These numerical cutoffs are frozen before final generation; they do not guarantee the same alert fraction on a different population. Rank metrics are average precision, trapezoidal PR-AUC and ROC-AUC. Undefined denominators are JSON null. Category recall at the F1 threshold includes transaction and scenario support. Seed summaries use population standard deviation, not confidence intervals.

## False-positive analysis

Only validation labels enter these diagnostics. Reports compare false positives and correctly unflagged normal records at the F1 threshold and all exact budgets. Grouping covers amount/fee intervals, input/output counts, UTC hour/weekday, score quantiles, and the number of globally observed transactions in `[t-60 seconds,t)`. All simultaneous transactions are excluded from each other's history. Appending future records cannot change earlier intensity. This global diagnostic is not wallet activity and never becomes a model input.

Reports provide counts, within-bin normal FPR, feature distributions and up to eight highest-score synthetic false positives per model/operating point. Example identifiers are local validation row references, not wallet identities. Candidate explanations are hypotheses, not causal findings. No difficult normal records are removed.

## Reproduction and preservation

PowerShell, repository root, existing venv and `backend/requirements-ml-lock.txt`:

```powershell
Push-Location backend
..\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_ml_tuning.py
..\venv\Scripts\python.exe -B -m app.ml.tuning tune --config ../configs/ml_tuning.json
# Review validation reports; all decision artifacts are already sealed.
..\venv\Scripts\python.exe -B -m app.ml.final_evaluation inventory --config ../configs/ml_final_405.json
..\venv\Scripts\python.exe -B -m app.ml.final_evaluation reserve --config ../configs/ml_final_405.json
..\venv\Scripts\python.exe -B -m app.ml.final_evaluation evaluate --config ../configs/ml_final_405.json
..\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
Pop-Location
.\venv\Scripts\python.exe -B -m pip check
```

The baseline corpora and frozen artifacts must already exist; see `ml_anomaly_detection.md` for original reproduction commands. Do not run baseline preparation over existing files. Tuning reads their recorded hashes, never training labels or historical test labels. Existing baseline fitting/evaluation APIs remain unchanged.

All new output directories must be unused. To reproduce the fixed experiment again, copy the tuning JSON and change only `run_dir`, `report_dir` and `final_data_dir` to unused paths. Keep seeds, grid, budget and policies unchanged; this is a reproducibility run, not a newly untouched test. Failed attempts retain their reservation/artifacts for diagnosis; do not delete them to conceal retries. Outputs are never automatically overwritten. Source changes after freezing prohibit final evaluation.

`artifacts/ml/tuning/` contains ignored candidate/selected models, detailed predictions and lifecycle markers. `data/ml/tuning/` contains ignored fresh corpora. Both are covered by existing ignore rules. Compact protocol, search, selection, validation, false-positive, final manifest and final evaluation reports live under `reports/ml/tuning/run-001/`. No new dependencies are required.

## Limits

Independent generation produces disjoint TXIDs, wallets and raw scenario IDs, while actor IDs are corpus-scoped local names. It does not introduce new scenario mechanisms: train, validation and final share the unchanged generator. Counts, transaction shapes, fee construction and scenario timing may carry synthetic shortcuts. Calendar features also change with observation windows. Identity/time audits and metadata exclusion cannot prove absence of such statistical shortcuts. No generator/label edits are made to mask these limits. No real-world deployment accuracy, wallet ownership or criminality is inferred.

Graph-based wallet/transaction relationships and causal temporal analysis remain the next separate milestone. Frontend, API changes and an ensemble are outside this implementation.

## Approved seed amendment and fixture audit

On 2026-09-27 the user approved changing only the reserved final seed from 404 to 405, keeping April dates and 15,300/2,700 counts. Early small regression fixtures reused 404; no fixture metrics drove configuration selection. Future generated lifecycle fixtures use 9404. Amendment tests use mocked literal identities and never generate seed 405.

`app.ml.final_evaluation` implements an additive amendment without modifying the original tuning source, fitted models, preprocessing, thresholds, scores, selection rule or comparator policies. The reservation binds the original freeze hash, selected artifacts, new evaluator source, fixture inventory and amendment configuration. The 36 production fits are not repeated. The old `app.ml.tuning final` command is historical and must not be used for this amended experiment.

The inventory includes all three original partitions, tracked v1/v2 datasets, retained pytest transaction/group files, reconstruction of known deleted/generated fixtures (including 404), and a conservative identity set for handwritten fixtures. Label columns in pre-existing raw v1/v2 files are excluded from the identity data; historical ML label-only sidecars are not opened. Tracked v2 ground-truth sidecars supply grouping identities only. Only final scoring/evaluation later consumes final labels. The inventory checks TXIDs, wallet addresses, corpus-scoped actors/scenarios and unscoped scenario hashes. Legacy fixtures without actor/scenario metadata report that absence rather than inventing identities. Unknown external/private fixtures cannot be audited.

Train/validation/historical-test and tracked dataset periods must precede the final corpus. Independent regression fixtures may intentionally reuse the April calendar window; overlaps are explicitly reported, not treated as chronological training/test splits. Corpus scoping distinguishes local actor names and is not evidence of different real-world owners; zero wallet and raw-scenario overlaps provide additional checks.

`inventory` and `reserve` run before final generation. `evaluate` verifies both freezes, takes an exclusive one-shot reservation, generates once, audits every reference population before scoring, scores all seven unchanged models, and only then reads final labels. Any failed audit writes a failure record and stops; there is no retry or automatic seed replacement. Detailed inventory and score files are ignored; compact manifest, seed-change and final-result reports are retained.

For a fresh exact reproduction, use unused tuning output paths, then copy the amendment config and match its run/report paths plus unused final/inventory paths. This reproduces a published synthetic experiment; seed 405 is no longer an unseen test after publication. Do not overwrite existing artifacts or rerun search to choose better final results.
