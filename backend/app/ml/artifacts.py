"""Trusted local joblib artifacts with explicit compatibility and integrity checks."""
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import joblib
import numpy as np
from .schema import ROOT, FEATURES, FEATURE_VERSION, digest, write_json


def environment():
    return {"python": platform.python_version(), **{name: importlib.metadata.version(name) for name in
            ('numpy', 'pandas', 'scipy', 'scikit-learn', 'joblib', 'threadpoolctl')}}


def source_provenance():
    files = sorted((ROOT/'backend/app/ml').glob('*.py')) + [ROOT/'scripts/prepare_ml_datasets.py', ROOT/'scripts/dataset_v2.py', ROOT/'scripts/btc_synthetic_dataset_generator.py']
    files += sorted((ROOT/'backend/app/features').glob('*.py')) + sorted((ROOT/'backend/app/ingestion').glob('*.py')) + [ROOT/'backend/app/money.py']
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=False)
    return {"git_revision": result.stdout.strip() or None,
            "source_hashes": {str(p.relative_to(ROOT)).replace('\\','/'): digest(p) for p in files}}


def save_artifact(path, model, threshold, metadata):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    joblib.dump(model, path/'pipeline.joblib', compress=3)
    write_json(path/'threshold.json', threshold)
    preprocessor = model.named_steps['preprocessing'] if hasattr(model, 'named_steps') else model.preprocessor
    manifest = {"artifact_version": 1, "feature_schema_version": FEATURE_VERSION, "features": FEATURES,
                "environment": environment(), "preprocessing": {"medians": preprocessor.medians_.tolist(),
                "log_features": preprocessor.log_features, "btc_multiplier": preprocessor.btc_multiplier, "scaling": "none"},
                "score_direction": "negative_score_samples_higher_is_more_anomalous", **metadata,
                "files": {name: digest(path/name) for name in ('pipeline.joblib', 'threshold.json')}}
    write_json(path/'manifest.json', manifest)
    return manifest


def load_artifact(path):
    path = Path(path)
    manifest = json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('artifact_version') != 1 or manifest.get('feature_schema_version') != FEATURE_VERSION or manifest.get('features') != FEATURES:
        raise ValueError('incompatible artifact feature schema')
    if manifest['environment'] != environment():
        raise ValueError('artifact requires the recorded Python/package versions')
    if set(manifest['files']) != {'pipeline.joblib', 'threshold.json'}:
        raise ValueError('invalid artifact file inventory')
    for name, expected in manifest['files'].items():
        if digest(path/name) != expected:
            raise ValueError('artifact checksum mismatch')
    threshold = json.loads((path/'threshold.json').read_text(encoding='utf-8'))
    if threshold.get('operator') != '>=' or threshold.get('partition') != 'validation' or not np.isfinite(threshold['threshold']):
        raise ValueError('invalid threshold metadata')
    # Only load artifacts produced locally or otherwise explicitly trusted.
    return joblib.load(path/'pipeline.joblib'), threshold, manifest


def freeze_run(run, config, corpus_manifest, artifact_names, details):
    run = Path(run)
    files = {}
    for name in artifact_names:
        for file in ('pipeline.joblib', 'threshold.json', 'manifest.json'):
            relative = f'{name}/{file}'
            files[relative] = digest(run/relative)
    frozen = {"status": "frozen", "config": config, "corpus_manifest": corpus_manifest,
              "artifacts": artifact_names, "files": files, **details}
    write_json(run/'frozen.json', frozen)
    return frozen


def verify_frozen(run):
    run = Path(run)
    frozen = json.loads((run/'frozen.json').read_text(encoding='utf-8'))
    if frozen.get('status') != 'frozen':
        raise ValueError('run is not frozen')
    expected = {f'{name}/{file}' for name in frozen['artifacts'] for file in ('pipeline.joblib','threshold.json','manifest.json')}
    if set(frozen['files']) != expected:
        raise ValueError('incomplete frozen inventory')
    for relative, value in frozen['files'].items():
        candidate = (run/relative).resolve()
        if not candidate.is_relative_to(run.resolve()) or digest(candidate) != value:
            raise ValueError('frozen artifact has changed')
    return frozen
