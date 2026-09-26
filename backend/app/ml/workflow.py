"""Offline experiment lifecycle: train/calibrate/freeze, then separate test evaluation."""
import json
from pathlib import Path
import time
import pandas as pd
from ..ingestion import ingest_file
from .schema import ROOT, FEATURES, from_transactions, digest, write_json, validate_config
from .splits import audit_partitions
from .training import fit_model
from .scoring import risk_scores, score_transactions
from .thresholds import calibrate
from .baselines import RobustDeviation
from .evaluation import align_truth, evaluate, seed_summary, save_plots
from .artifacts import save_artifact, load_artifact, freeze_run, verify_frozen, source_provenance


def read_verified(data, name, suffix, manifest):
    path = data / f'{name}.{suffix}.jsonl'
    if digest(path) != manifest['corpora'][name]['files'][path.name]:
        raise ValueError(f'corpus checksum mismatch: {path.name}')
    if suffix == 'transactions':
        # Check raw schema before canonical ingestion can discard unknown columns.
        raw = pd.read_json(path, lines=True)
        if {'label','anomaly_type','actor_id','scenario_id'} & set(raw.columns):
            raise ValueError('transaction corpus contains forbidden metadata')
        result = ingest_file(path)
        if result.ground_truth is not None or result.report.rejected_rows or result.report.duplicate_rows or result.report.valid_rows != manifest['corpora'][name]['records']:
            raise ValueError('corpus ingestion did not preserve every record')
        return result.transactions
    return pd.read_json(path, lines=True)


def training_run(config, root=ROOT):
    validate_config(config)
    start = time.perf_counter()
    data, run = root/config['data_dir'], root/config['run_dir']
    if run.exists():
        raise ValueError('run directory already exists; use a new run_dir to preserve frozen experiments')
    manifest = json.loads((data/'manifest.json').read_text(encoding='utf-8'))
    if manifest['experiment_version'] != config['experiment_version']:
        raise ValueError('experiment manifest mismatch')
    for name, spec in config['corpora'].items():
        if manifest['corpora'][name]['generation'] != spec:
            raise ValueError('generation configuration mismatch')
    partitions = {name: (read_verified(data, name, 'transactions', manifest), read_verified(data, name, 'groups', manifest))
                  for name in ('train','validation','test')}
    audit = audit_partitions(partitions)
    if audit != manifest['split_audit']:
        raise ValueError('partition audit differs from generation manifest')
    _, train = from_transactions(partitions['train'][0])
    validation_ids, validation = from_transactions(partitions['validation'][0])
    preparation_seconds = time.perf_counter()-start
    provenance = source_provenance()
    run.mkdir(parents=True)
    fitted, timings = {}, {}
    # Fit every seed before opening validation labels. Test labels are never opened here.
    for seed in config['model_seeds']:
        started = time.perf_counter()
        fitted[f'iforest-{seed}'] = fit_model(train, config, seed)
        timings[f'iforest-{seed}'] = {'fit_seconds': time.perf_counter()-started}
    started = time.perf_counter()
    reference_model = fitted[f"iforest-{config['reference_seed']}"]
    preprocessor = reference_model.named_steps['preprocessing']
    fitted['heuristic'] = RobustDeviation(preprocessor, **config['heuristic']).fit(train)
    timings['heuristic'] = {'fit_seconds': time.perf_counter()-started}
    validation_truth = read_verified(data, 'validation', 'labels', manifest)
    y, categories = align_truth(validation_ids, validation_truth)
    groups = partitions['validation'][1].set_index('txid').loc[list(validation_ids)].scenario_id.to_numpy()
    validation_results, artifact_metadata = {}, {}
    for name, model in fitted.items():
        started = time.perf_counter()
        scores = risk_scores(model, validation)
        timings[name]['validation_score_seconds'] = time.perf_counter()-started
        started = time.perf_counter()
        threshold = calibrate(scores, y, partition='validation')
        timings[name]['calibration_seconds'] = time.perf_counter()-started
        validation_results[name] = evaluate(scores, y, categories, validation_ids, threshold['threshold'], config['alert_budgets'], groups)
        metadata = {'model_version': f"{config['experiment_version']}/{name}", 'seed': int(name.split('-')[-1]) if name.startswith('iforest') else None,
                    'training_rows': len(train), 'feature_dimensions': len(FEATURES), 'config': config,
                    'provenance': provenance, 'training_data_hash': manifest['corpora']['train']['files']['train.transactions.jsonl']}
        artifact_metadata[name] = save_artifact(run/name, model, threshold, metadata)
    details = {'preparation_seconds': preparation_seconds, 'timings': timings, 'validation': validation_results,
               'feature_shapes': {'train': list(train.shape), 'validation': list(validation.shape), 'test': [len(partitions['test'][0]),len(FEATURES)]},
               'training_total_seconds': time.perf_counter()-start, 'provenance': provenance}
    frozen = freeze_run(run, config, manifest, list(fitted), details)
    write_json(root/config['report_dir']/'training_summary.json', {**details, 'thresholds': {name: json.loads((run/name/'threshold.json').read_text()) for name in fitted},
               'frozen_sha256': digest(run/'frozen.json'), 'artifact_files': {name: value['files'] for name, value in artifact_metadata.items()}})
    return frozen


def evaluate_run(run, root=ROOT, plots=True):
    start = time.perf_counter()
    run = Path(run)
    frozen = verify_frozen(run)
    frozen_hash = digest(run/'frozen.json')
    config, manifest = frozen['config'], frozen['corpus_manifest']
    # All artifacts, including compatibility, must pass before the first test-label read.
    models = {name: load_artifact(run/name) for name in frozen['artifacts']}
    data = root/config['data_dir']
    tx = read_verified(data, 'test', 'transactions', manifest)
    ids, matrix = from_transactions(tx)
    groups = read_verified(data, 'test', 'groups', manifest).set_index('txid').loc[list(ids)].scenario_id.to_numpy()
    scores, timings = {}, {}
    for name, (model, threshold, metadata) in models.items():
        started = time.perf_counter()
        scored = score_transactions(model, matrix, ids, threshold['threshold'], metadata['model_version'])
        timings[name] = time.perf_counter()-started
        scored.to_csv(run/name/'test_scores.csv', index=False)
        scores[name] = scored.anomaly_score.to_numpy()
    # First test-label read: the complete run and all scores are already frozen.
    truth = read_verified(data, 'test', 'labels', manifest)
    y, categories = align_truth(ids, truth)
    metrics = {}
    for name, values in scores.items():
        metrics[name] = evaluate(values, y, categories, ids, models[name][1]['threshold'], config['alert_budgets'], groups)
        if plots:
            save_plots(run/name/'plots', values, y)
    verify_frozen(run)
    if digest(run/'frozen.json') != frozen_hash:
        raise ValueError('frozen run changed')
    report = {'experiment_version': config['experiment_version'], 'reference_model': f"iforest-{config['reference_seed']}",
              'frozen_sha256': digest(run/'frozen.json'), 'test_feature_shape': list(matrix.shape),
              'models': metrics, 'seed_summary': seed_summary([metrics[f'iforest-{seed}'] for seed in config['model_seeds']]),
              'test_scoring_seconds': timings, 'evaluation_total_seconds': time.perf_counter()-start,
              'interpretation': 'Synthetic injected-scenario performance, not real-world criminality or deployment accuracy. No test-based model selection.'}
    write_json(run/'evaluation.json', report)
    write_json(root/config['report_dir']/'evaluation.json', report)
    return report


def score_file(run, input_path, output, seed=None):
    frozen = verify_frozen(run)
    seed = frozen['config']['reference_seed'] if seed is None else seed
    name = f'iforest-{seed}'
    if name not in frozen['artifacts']:
        raise ValueError('seed not present in frozen experiment')
    model, threshold, metadata = load_artifact(Path(run)/name)
    result = ingest_file(input_path)
    if result.report.status == 'failed' or result.report.rejected_rows or result.report.duplicate_rows:
        raise ValueError('scoring requires successful ingestion without rejected/duplicate records')
    ids, matrix = from_transactions(result.transactions)
    out = score_transactions(model, matrix, ids, threshold['threshold'], metadata['model_version'])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return {'rows': len(out), 'flagged': int(out.flagged.sum()), 'output': str(output)}
