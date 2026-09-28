# Bitcoin transaction monitoring and analysis

Smart India Hackathon 2026 - PS 26146.

Implemented: CSV/JSON/JSONL ingestion, validation and deduplication, FastAPI health/upload routes, deterministic synthetic Dataset v2, transaction/wallet feature extraction, offline transaction-only Isolation Forest anomaly detection, bounded tuning, validation false-positive analysis and frozen final evaluation. Graph analysis and frontend are not implemented.

## Repository

- `backend/app/ingestion/`: readers, canonical schema, validation, reports, CLI.
- `backend/app/main.py`, `service.py`: existing FastAPI and upload handling.
- `backend/app/money.py`: exact satoshi conversion.
- `backend/app/features/`: behavioural tables, separate investigative context, explicit ML selections and CLI.
- `backend/app/ml/`: strict preprocessing, Isolation Forest, calibration, heuristic, evaluation, artifact loading and offline CLI.
- `configs/ml_baseline.json`, `scripts/prepare_ml_datasets.py`: fixed experiment settings and independent corpora.
- `reports/ml/`: compact reproducibility manifests and evaluation summaries; large ML data/models are Git-ignored.
- `scripts/btc_synthetic_dataset_generator.py`: generation CLI and retained legacy v1 generator.
- `scripts/dataset_v2.py`: deterministic v2 actors and complete anomaly scenarios.
- `scripts/validate_pipeline.py`: generation, full validation, feature exports, quality diagnostics and API checks.
- `data/btc_synthetic_dataset.csv`: preserved v1 dataset (8,726 records).
- `data/v2/`: development (18,000) and regression (1,000) CSV/JSONL datasets, ground-truth sidecars, manifests, features and reports.
- `backend/tests/`: ingestion, API, generator, monetary and feature tests.

Read [Dataset v2](docs/dataset_v2.md), [feature definitions](docs/features.md), [measured milestone results](docs/milestone_validation.md), and the [ML experiment guide](docs/ml_anomaly_detection.md).

The Isolation Forest ML milestone is complete. The frozen synthetic [ML results](docs/ml_results.md) for seed 42 are precision 18.79%, recall 55.22%, F1 0.2804 and false-positive rate 42.12%. The heuristic baseline performed better (F1 0.3291). Rapid-layering recall (19.63%) and peeling recall (27.65%) remain weak. All three fixed seeds, category recall and 1%/5%/10% alert-budget precision are reported without test-based tuning. These findings make no real-world deployment accuracy claim.

The final read-only audit passed 160 tests plus 75 subtests in 52.90s, with zero failures/skips and the known Starlette/httpx warning, preserving all 105 prior tests. Full corpus regeneration and experiment model retraining were not rerun during that audit; saved predictions and reported evaluation metrics were independently verified. Regression tests exercised isolated temporary fixtures. The earlier implementation-validation run took 63.16s.

## Environment and commands

Commands below are PowerShell commands from the repository root. The existing `venv` is used. Runtime dependencies are in `backend/requirements.txt`; test/reporting dependencies are in `backend/requirements-dev.txt`. The ML milestone added scikit-learn, joblib and matplotlib, with a tested environment snapshot in `backend/requirements-ml-lock.txt`. Python 3.13.14 was used for validation. For a fresh environment, create a virtual environment and install the dev requirements, or the pinned lock file for exact ML reproduction.

```powershell
Set-Location -LiteralPath 'C:\Users\Ayub Asad\Desktop\sih project'
$env:PYTHONDONTWRITEBYTECODE = '1'

# Complete reproduction: both datasets, features, manifests, quality and API checks
.\venv\Scripts\python.exe -B scripts\validate_pipeline.py

# Full test suite
Push-Location backend
..\venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
Pop-Location
```

Individual steps:

```powershell
# Dataset generation only (default seed 42; default counts 15,300 + 2,700)
.\venv\Scripts\python.exe -B scripts\btc_synthetic_dataset_generator.py --schema-version 2 --seed 42 --both --out data/v2/development.csv
.\venv\Scripts\python.exe -B scripts\btc_synthetic_dataset_generator.py --schema-version 2 --seed 42 --n-normal 850 --n-anomalous 150 --both --out data/v2/regression.csv

# Reproduce v1 separately, without overwriting the preserved file
.\venv\Scripts\python.exe -B scripts\btc_synthetic_dataset_generator.py --schema-version 1 --seed 42 --n-normal 8000 --n-anomalous 800 --out data/regenerated_v1.csv

Push-Location backend
..\venv\Scripts\python.exe -B -m app.ingestion ../data/v2/development.csv --json
..\venv\Scripts\python.exe -B -m app.features ../data/v2/development.csv --out-dir ../data/v2 --burst-window-seconds 60
# Optional local API server; stop with Ctrl+C
..\venv\Scripts\python.exe -B -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Pop-Location
```

`validate_pipeline.py --dataset-only` omits feature exports but still checks generated data and API uploads. The report's timings are measured and will vary by machine/load. Generation uses fresh seed-initialized instances; deterministic files are expected with the same implementation and runtime. Validation reports include variable timings and are not byte-identical.

## Programmatic interface

Run from `backend/`:

```python
from app.ingestion import ingest_file
from app.features import extract_features, ml_ready_frame

result = ingest_file('../data/v2/development.csv')
tables = extract_features(result.transactions)
transaction_matrix = ml_ready_frame(tables.transaction_features, 'transaction')
wallet_matrix = ml_ready_frame(tables.wallet_features, 'wallet')
# result.ground_truth stays separate for later evaluation.
```

API response shape and status handling remain unchanged: `GET /health`; multipart `POST /ingest` with optional `?format=csv|json|jsonl`; HTTP 200 for at least one valid row, 413 for oversized upload, 415 unsupported format, 422 unusable data. Upload responses are ingestion reports, not feature tables. XML remains a reader extension target.

## Limits and next milestone

These are synthetic, internally consistent records, not a UTXO ledger, validated blockchain transactions or representative Bitcoin traffic. Amounts include change. Network links are observations, not ownership. Legacy exact flows are unavailable. Whole-window wallet aggregates are not causal online features. Port/geo scenarios may not be detectable from the default behavioural features alone. Address validation is structural, not checksum validation; coinbase and addressless outputs remain unsupported.

The ML baseline uses 10 numerical transaction features, independent training/validation/test corpora with seeds 101/202/303, and model seeds 42/43/44. Training is normal-only by generation, preprocessing is fitted only on training data, and threshold calibration uses validation labels only. Test labels are opened only after all artifacts and thresholds are frozen. See the [ML guide](docs/ml_anomaly_detection.md) for installation, generation, training, evaluation, scoring and regeneration of ignored artifacts. Synthetic anomaly scores are not evidence of criminal activity or calibrated real-world probabilities.

Next milestone: graph-based investigation of wallet relationships, transaction chains and temporal patterns, integrated with the existing ML anomaly scores. It is planned, not implemented in this handoff. Preserve the frozen ML baseline and distinguish address relationships from verified ownership.

## Hyperparameter tuning and false-positive analysis

The bounded 12-configuration search fitted seeds 42/43/44 (36 fits) and selected 200 trees, 1,024 samples, max_features 0.8, no bootstrap. See [the protocol and reproduction commands](docs/ml_tuning.md), [validation false-positive findings](docs/ml_false_positive_analysis.md), and [all measured results](docs/ml_tuning_results.md).

The approved fresh final corpus uses seed 405: April 2025, 15,300 normal and 2,700 injected anomalous transactions. Seed 404 was replaced because early regression fixtures used it; the original model freeze stayed unchanged. All 21 reference populations passed identity audits before scoring. Required chronological periods do not overlap; independent April fixture windows are explicitly disclosed.

On the same final population, mean top-1% precision rose from 27.59% (original IF) to 30.19% (tuned IF), with recall only 1.84% versus 2.01%. Mean F1 improved from 0.2871 to 0.2967 and FPR fell from 39.00% to 34.63%, but mean threshold recall declined from 53.80% to 51.62%. The heuristic retains higher F1 (0.3347). Tuned seed-42 rapid-layering/peeling recall is only 11.11%/19.75%. This is a modest synthetic ranking improvement, not deployment accuracy or evidence of criminality.

Final checks: 199 tests plus 75 subtests passed in 195.75s, zero failures/skips, one known Starlette/httpx warning; pip check passes. All 58 protected baseline/data files and 130 frozen tuning files are unchanged. Final evaluation ran once in 20.63s; no production refitting, retuning, recalibration or ensemble was performed. Existing ingestion/API/feature contracts are unchanged. Graph investigation remains a separate next milestone.
