# Transaction anomaly detection experiment

This milestone implements an offline, transaction-only Isolation Forest baseline. The estimator is unsupervised; its external alert threshold is calibrated with validation labels. Synthetic injected-scenario labels are not verified criminality. Scores are not probabilities, and performance is not an estimate of real Bitcoin deployment accuracy.

## Reproduction

Run from the repository root in PowerShell using the existing `venv`. The tested environment is pinned in `backend/requirements-ml-lock.txt`; it includes runtime, reporting and test dependencies. Installation needs package-index access; generation, fitting, scoring and evaluation run offline afterward.

```powershell
$env:MPLCONFIGDIR = Join-Path (Get-Location) 'artifacts/ml/matplotlib-cache'
.\venv\Scripts\python.exe -B -m pip install -r backend/requirements-ml-lock.txt
.\venv\Scripts\python.exe -B -m pip check
.\venv\Scripts\python.exe -B scripts/prepare_ml_datasets.py --config configs/ml_baseline.json
Push-Location backend
..\venv\Scripts\python.exe -B -m app.ml train --config ../configs/ml_baseline.json
..\venv\Scripts\python.exe -B -m app.ml evaluate --run ../artifacts/ml/baseline
..\venv\Scripts\python.exe -B -m app.ml score --run ../artifacts/ml/baseline --input ../data/v2/development.csv --out ../artifacts/ml/development_scores.csv
..\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
Pop-Location
```

The explicit Matplotlib cache location keeps plotting writes inside the workspace. The first validation run used Matplotlib's temporary-cache fallback because the default user-profile cache was not writable; plots and evaluation still completed.

Training refuses to overwrite an existing run directory. For another reproduction, copy `configs/ml_baseline.json` to a new configuration, change `run_dir` and `report_dir` to unused paths, and pass that configuration to `train`. Keep experimental settings fixed when checking reproducibility. Configuration paths are relative to the repository root; CLI input/output paths are relative to the current directory. Evaluation uses the configuration embedded in the frozen run, not a subsequently edited configuration file. `score --seed 43` or `--seed 44` selects another already-frozen model; the default reference is always 42.

Large generated corpora are in ignored `data/ml/`. Fitted artifacts, detailed score CSVs, curve CSVs and plots are in ignored `artifacts/ml/`. Compact generation manifests, training summaries and final evaluation summaries are in `reports/ml/` for source control. The original tracked v1 and v2 data are preserved. Regenerating corpora reproduces content hashes with the recorded runtime/code; timing fields vary. Model scores and thresholds are tested for determinism; binary serialization and timing metadata are not promised byte-identical across environments.

## Independent corpora and label boundaries

| Corpus | Seed | Start UTC | Normal | Injected anomalies |
|---|---:|---|---:|---:|
| Train | 101 | 2025-01-01 | 15,300 | 0 |
| Validation | 202 | 2025-02-01 | 15,300 | 2,700 |
| Test | 303 | 2025-03-01 | 15,300 | 2,700 |

`prepare_ml_datasets.py` uses the existing v2 generator and its explicit start-time argument. It serializes all generated records; no scenario is truncated or split. Transaction files omit labels and actor/scenario metadata. Separate `*.groups.jsonl` files contain only transaction IDs and corpus-scoped grouping identities; separate `*.labels.jsonl` files contain evaluation truth. Identity scope distinguishes separately generated actors with reused names such as `actor-0001`; wallet-address and raw-scenario checks additionally enforce actual nonoverlap.

Preparation and pre-training audit require disjoint transaction IDs, wallets, scoped actors/scenarios and raw scenario IDs across every pair of partitions; exact grouping coverage; one generating actor per scenario; and strict chronological ordering. Hashes bind the transaction, grouping and label sidecars to their manifests. Training verifies transaction/grouping hashes, never reads training labels, and never reads or hashes test-label files. Preparation necessarily creates and hashes those files, but does not use them to tune an experiment.

The baseline normal partition exists by generation configuration, not by filtering a mixed dataset with labels. All three models fit before validation labels are opened. Validation labels calibrate thresholds and produce validation metrics only. Training freezes all model binaries, thresholds and metadata into a checksum inventory. Evaluation validates every artifact, scores test features, and only then opens test labels. It never fits, changes settings or recalibrates. All three seeds are reported; no best test seed is selected.

The prior v2 development and regression files are unsuitable as independent ML splits: all 1,000 regression TXIDs overlap development. The development records also form one connected component under shared scenario/actor/wallet relationships. A tentative chronological 60/20/20 split crossed one scenario and 510 actors. This milestone therefore uses independent corpora instead of a random row split. Independent populations in later calendar windows test transfer within the same synthetic generator, not real temporal drift.

## Feature schema and preprocessing

`transaction-behaviour-v1` uses exactly the existing ordered allowlist:

```text
amount_btc, fee_btc, fee_rate_sat_vb, num_inputs, num_outputs,
fee_to_amount_ratio, input_output_count_ratio,
hour_of_day_utc, day_of_week_utc, is_night_utc
```

Identifiers, raw timestamps, source lineage, all IP/port/country/ASN context, wallet features, actor/scenario identities, labels and anomaly types are excluded. Canonical transaction features depend only on each transaction; appending future records cannot change an earlier row. Model fitting requires the exact ordered numerical schema and rejects extra, missing, duplicate or reordered columns, strings/booleans, infinities, negative values, fractional counts, invalid calendar ranges and inconsistent night indicators.

Only optional fee rates and undefined legacy input/output-count ratios may be missing. Their medians are learned on training data alone; an entirely missing training column fails explicitly. Missing required features fail rather than being fabricated. No missingness indicator is added. New missingness patterns are not automatically representative of the complete synthetic training data.

The fixed transform converts amount/fee BTC values to satoshi units and applies `log1p`; fee rates and both ratios also receive `log1p`. Counts and calendar features remain unchanged. There is no clipping or scaler. Finite checks run before and after transformation, including a float32 representability check for the forest. Accounting remains integer-satoshi upstream; transformed statistics are floating-point model inputs. Existing `ml_ready_frame` behaviour is unchanged.

Amounts include change and are not net economic transfers. The hour/weekday representations have calendar discontinuities and `is_night_utc` is redundant. Legacy amount semantics can differ; successful schema validation does not establish calibration for legacy or real data.

## Fitting, calibration and comparison

Versioned `configs/ml_baseline.json` records corpus seeds/dates/counts, feature version, transformations, 300 trees, 256 samples per tree, all features, no bootstrap, one worker, model seeds 42/43/44, reference seed 42, threshold policy and alert budgets.

`contamination="auto"` is retained because decision-making uses an external threshold. It is not set to the synthetic 15% anomaly prevalence. The model's native offset does not determine application flags:

```text
anomaly_score = -score_samples(features)
flagged = anomaly_score >= threshold
```

The threshold maximizes validation F1 over all distinct validation scores. Ties prefer lower validation false-positive rate, then higher threshold. Equal scores are never split by the threshold. Calibration rejects training/test partitions and validation data lacking either class. There is no post-calibration refit.

The fixed heuristic uses the first seven non-calendar features after the same fitted preprocessing. Its risk score is the maximum absolute deviation from each training median, divided by its training IQR. A zero IQR uses scale 1.0. Its threshold follows the same validation rule. This comparator's preprocessing is shared with the reference forest but no evaluation label enters its centers/scales.

Normal-only fitting is an optimistic synthetic reference-population assumption. An unlabeled mixed-data experiment would avoid requiring known clean training data, but common injected patterns could become part of its reference distribution. No mixed-data experiment or test-informed feature/model search is performed here.

## Evaluation definitions

Reports contain precision, recall, F1, TN/FP/FN/TP, false-positive rate `FP/(FP+TN)`, average precision, trapezoidal PR-AUC and ROC-AUC. Average precision is distinguished from trapezoidal integration. Rank AUC metrics are unavailable without both classes. Precision is unavailable without alerts; recall is unavailable without positive labels; absent categories have null recall and zero support. Category recall counts flagged transactions in each category, with both transaction and scenario support. Per-seed results and population standard deviation/mean/min/max across the three fixed seeds are retained; these seed variations are not population confidence intervals.

Fixed test alert budgets are 1%, 5% and 10%. The count is `ceil(budget * test_rows)`. Scores sort descending, with TXID ascending breaking ties deterministically. These budget lists can split score ties to meet an exact budget, unlike threshold flags. Each report records actual alerts, true positives and precision. Test labels measure these predeclared lists; they never choose a budget or change a model. On 18,000 records, budgets mean 180, 900 and 1,800 alerts.

Per-class score quantiles are in compact reports. Detailed precision-recall curves and distribution plots are generated locally during evaluation. The 15% synthetic anomaly prevalence affects precision and the F1-optimal threshold. Deployment prevalence, acceptable FPR and alert capacity remain unknown; no operational target or accuracy guarantee is claimed.

## Artifacts and integration contract

Each model directory contains `pipeline.joblib`, `threshold.json` and `manifest.json`. Manifests include ordered features/version, learned imputation values, transforms, package/Python versions, generation/configuration provenance, source hashes and checksums. `frozen.json` binds all model artifacts and thresholds before test evaluation. Joblib artifacts are trusted local executable Python objects: only load trusted artifacts, using the recorded versions. Loading detects checksum, schema and environment mismatches.

Transaction output is `txid, anomaly_score, threshold, flagged, model_version, feature_schema_version`. Scoring uses the canonical ingestion boundary and rejects uploads with rejected/duplicate transactions instead of silently scoring a subset. Labels present in a source file remain in ingestion's separate truth table and do not reach the scorer. `from_transactions`, `fit_model`, `score_transactions` and artifact functions are framework-independent. Existing FastAPI routes and ingestion responses are unchanged; future API/graph integrations can consume these interfaces. There is no graph or frontend implementation.

## Causal wallet extension: design only

Existing wallet aggregates describe the entire supplied observation window and cannot be joined into historical model rows. A future causal extension must compute wallet activity strictly before timestamp `t`: distinct prior transaction counts, trailing-window counts, time since prior activity, prior amount statistics and exact directional allocations. Score all transactions tied at `t` before updating state for any of them. Repeated allocations aggregate but each wallet counts once per transaction; legacy missing allocations remain unavailable. Feature tests must prove invariance under appending future transactions and deterministic handling of tied timestamps. A cold-start policy and deterministic per-transaction aggregation over involved wallets need their own schema version and evaluation. No wallet ownership or criminality labels are inferred.

## Known limits

The generator has no UTXO ledger, calibrated GeoIP or real ownership information. Port/geo categories deliberately depend on context excluded from these features; rapid chains, dust bursts and peeling also contain sequence information absent from transaction-only modelling. Cross-category performance can therefore be poor and must be reported. Independent corpora still share generator mechanisms and may share synthetic statistical shortcuts. Future real data require separate adaptation, calibration and validation. Existing coinbase/addressless-output/XML limitations remain.
