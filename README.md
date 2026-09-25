# Bitcoin transaction monitoring and analysis

Smart India Hackathon 2026 - PS 26146.

Implemented: CSV/JSON/JSONL ingestion, validation and deduplication, FastAPI health/upload routes, deterministic synthetic Dataset v2, and transaction/wallet feature extraction. ML training, graph analysis and frontend are not implemented.

## Repository

- `backend/app/ingestion/`: readers, canonical schema, validation, reports, CLI.
- `backend/app/main.py`, `service.py`: existing FastAPI and upload handling.
- `backend/app/money.py`: exact satoshi conversion.
- `backend/app/features/`: behavioural tables, separate investigative context, explicit ML selections and CLI.
- `scripts/btc_synthetic_dataset_generator.py`: generation CLI and retained legacy v1 generator.
- `scripts/dataset_v2.py`: deterministic v2 actors and complete anomaly scenarios.
- `scripts/validate_pipeline.py`: generation, full validation, feature exports, quality diagnostics and API checks.
- `data/btc_synthetic_dataset.csv`: preserved v1 dataset (8,726 records).
- `data/v2/`: development (18,000) and regression (1,000) CSV/JSONL datasets, ground-truth sidecars, manifests, features and reports.
- `backend/tests/`: ingestion, API, generator, monetary and feature tests.

Read [Dataset v2](docs/dataset_v2.md), [feature definitions](docs/features.md), and [measured milestone results](docs/milestone_validation.md).

## Environment and commands

Commands below are PowerShell commands from the repository root. The existing `venv` was used; no dependencies were installed during this milestone. Runtime dependencies are in `backend/requirements.txt`; test dependencies are in `backend/requirements-dev.txt`. Python 3.13.14 was used for validation. For a fresh environment, create a virtual environment and install the dev requirements.

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

Next: Isolation Forest anomaly detection with leakage-safe evaluation, explicit missing-value policy, time/group separation and preprocessing fitted only on training data. No ML model was trained in this milestone.
