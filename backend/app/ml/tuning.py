"""Bounded validation-only tuning and sealed, one-shot fresh-test evaluation.

Run from backend: python -m app.ml.tuning tune|final --config ../configs/ml_tuning.json
"""
import argparse
import copy
from dataclasses import asdict
from datetime import datetime
import itertools
import json
from pathlib import Path
import random
import shutil
import sys
import time
import numpy as np
import pandas as pd
from .schema import ROOT, FEATURES, digest, from_transactions, load_config
from .workflow import read_verified
from .training import fit_model
from .thresholds import calibrate
from .scoring import risk_scores
from .evaluation import align_truth, seed_summary
from .artifacts import load_artifact, save_artifact, verify_frozen, environment, source_provenance
from .splits import audit_partitions
from .tuning_analysis import operating_metrics, budget_thresholds, false_positive_summary, operating_seed_summary


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def canonical(params):
    return json.dumps(params, sort_keys=True, separators=(',', ':'))


def validate_tuning(config):
    if config['model_seeds'] != [42, 43, 44] or config['search_budget'] != 12:
        raise ValueError('tuning requires 12 candidates and fixed seeds 42/43/44')
    if config['alert_budgets'] != [.01, .02, .05, .10] or config['ensemble'] is not False:
        raise ValueError('unsupported budgets or ensemble')
    if config['selection'] != {'primary': 'mean_validation_precision_at_1_percent',
            'minimum_mean_recall': .01, 'ties': ['mean_validation_f1_descending', 'canonical_configuration_ascending'],
            'infeasible': 'stop_without_final_evaluation'}:
        raise ValueError('selection policy differs from approved contract')
    if config['alert_rounding'] != 'ceil' or config['alert_tie_break'] != 'txid_ascending':
        raise ValueError('unsupported ranking policy')
    if config['threshold_policy'] != 'validation_f1_and_validation_budget_score_cutoffs_ge':
        raise ValueError('unsupported threshold policy')
    if config['comparison_policy'] != 'all_frozen_baseline_seeds_and_heuristic_same_population_original_f1_thresholds_validation_budget_cutoffs':
        raise ValueError('unsupported comparison policy')
    if config['activity_window_seconds'] != 60:
        raise ValueError('diagnostic window must be 60 seconds')
    spec = config['final_test']
    if spec['seed'] != 404 or spec['start_time'] != '2025-04-01T00:00:00+00:00':
        raise ValueError('reserved final seed/date changed')
    for field in ('normal', 'anomalous'):
        if type(spec[field]) is not int or spec[field] <= 0:
            raise ValueError('positive final counts required')
    grid = config['grid']
    if set(grid) != {'n_estimators', 'max_samples', 'max_features', 'bootstrap'}:
        raise ValueError('invalid search dimensions')
    for name, values in grid.items():
        if not values or len(set(values)) != len(values):
            raise ValueError('empty or duplicate grid values')
        if name in ('n_estimators', 'max_samples') and any(type(v) is not int or v <= 0 for v in values):
            raise ValueError('invalid integer parameter')
        if name == 'max_features' and any(type(v) not in (float, int) or not 0 < v <= 1 for v in values):
            raise ValueError('invalid max_features')
        if name == 'bootstrap' and any(type(v) is not bool for v in values):
            raise ValueError('invalid bootstrap')
    if type(config['search_seed']) is not int:
        raise ValueError('integer search seed required')
    return config


def sample_candidates(config, training_rows):
    keys = sorted(config['grid'])
    grid = [dict(zip(keys, values)) for values in itertools.product(*(config['grid'][k] for k in keys))]
    grid = sorted((p for p in grid if p['max_samples'] <= training_rows), key=canonical)
    if len(grid) < config['search_budget']:
        raise ValueError('insufficient unique configurations for search budget')
    return sorted(random.Random(config['search_seed']).sample(grid, config['search_budget']), key=canonical)


def select_candidate(candidates, *, partition, minimum_recall=.01):
    if partition != 'validation':
        raise ValueError('selection requires validation')
    feasible = [c for c in candidates if c['mean_top_1_recall'] >= minimum_recall]
    if not feasible:
        raise ValueError('no feasible candidate; final evaluation prohibited')
    return min(feasible, key=lambda c: (-c['mean_top_1_precision'], -c['mean_f1'], canonical(c['parameters'])))


def tuning_provenance():
    p = source_provenance()
    p['source_hashes']['backend/app/ml/tuning.py'] = digest(Path(__file__))
    p['source_hashes']['backend/app/ml/tuning_analysis.py'] = digest(Path(__file__).with_name('tuning_analysis.py'))
    return p


def checked_paths(config, root, baseline):
    root = Path(root).resolve()
    outputs = [root/config[k] for k in ('run_dir', 'report_dir', 'final_data_dir')]
    protected = [root/config['baseline_run'], root/baseline['data_dir'], root/baseline['report_dir'], root/'data/v2']
    for path in outputs:
        p = path.resolve()
        if not p.is_relative_to(root) or p == root:
            raise ValueError('outputs must stay inside experiment root')
        # Child tuning directories inside data/ml and reports/ml are intentional.
        if any(p == q.resolve() or q.resolve().is_relative_to(p) for q in protected):
            raise ValueError('output would replace protected directory')
        if p.is_relative_to((root/config['baseline_run']).resolve()) or p.is_relative_to((root/'data/v2').resolve()):
            raise ValueError('output inside protected artifact directory')
    for a, b in itertools.combinations(outputs, 2):
        if a.resolve().is_relative_to(b.resolve()) or b.resolve().is_relative_to(a.resolve()):
            raise ValueError('output directories overlap')
    return outputs


def tune(config, root=ROOT):
    started = time.perf_counter()
    validate_tuning(config)
    root = Path(root)
    baseline = load_config(root/config['baseline_config'])
    run, report, final_data = checked_paths(config, root, baseline)
    if any(p.exists() for p in (run, report, final_data)):
        raise FileExistsError('tuning output already exists; choose unused output paths')
    original = verify_frozen(root/config['baseline_run'])
    if original['config'] != baseline:
        raise ValueError('baseline configuration differs from frozen artifact')
    manifest = read_json(root/baseline['data_dir']/'manifest.json')
    if manifest != original['corpus_manifest']:
        raise ValueError('baseline corpus manifest changed')
    data = root/baseline['data_dir']
    partitions = {name: (read_verified(data, name, 'transactions', manifest), read_verified(data, name, 'groups', manifest))
                  for name in ('train', 'validation', 'test')}
    if audit_partitions(partitions) != manifest['split_audit']:
        raise ValueError('baseline partition audit changed')
    _, train = from_transactions(partitions['train'][0])
    ids, validation = from_transactions(partitions['validation'][0])
    y, categories = align_truth(ids, read_verified(data, 'validation', 'labels', manifest))
    groups = partitions['validation'][1].set_index('txid').loc[list(ids)].scenario_id.to_numpy()
    candidates = sample_candidates(config, len(train))
    run.mkdir(parents=True, exist_ok=False)
    report.mkdir(parents=True, exist_ok=False)
    exclusive_json(report/'protocol.json', config)
    exclusive_json(run/'sampled_configurations.json', candidates)
    results = []; budgets = config['alert_budgets']
    provenance = tuning_provenance()
    for index, parameters in enumerate(candidates):
        entry = {'candidate': f'candidate-{index:02d}', 'parameters': parameters, 'seeds': {}}
        for seed in config['model_seeds']:
            model_config = copy.deepcopy(baseline)
            model_config['model'].update(parameters)
            begin = time.perf_counter()
            model = fit_model(train, model_config, seed)
            fit_seconds = time.perf_counter()-begin
            scores = risk_scores(model, validation)
            threshold = calibrate(scores, y, partition='validation')
            cutoffs = budget_thresholds(scores, ids, budgets, partition='validation')
            metrics = operating_metrics(scores, y, categories, ids, threshold['threshold'], cutoffs, budgets, groups)
            name = f"{entry['candidate']}/iforest-{seed}"
            save_artifact(run/name, model, threshold, {'model_version': f"{config['experiment_version']}/{name}",
                'seed': seed, 'hyperparameters': model_config['model'], 'training_rows': len(train),
                'training_data_hash': manifest['corpora']['train']['files']['train.transactions.jsonl'],
                'provenance': provenance})
            entry['seeds'][str(seed)] = {'fit_seconds': fit_seconds, 'f1': metrics['f1'],
                'top_1': metrics['exact_review_budgets']['1%'], 'threshold': threshold, 'budget_cutoffs': cutoffs}
        entry['mean_top_1_precision'] = float(np.mean([s['top_1']['precision'] for s in entry['seeds'].values()]))
        entry['mean_top_1_recall'] = float(np.mean([s['top_1']['recall'] for s in entry['seeds'].values()]))
        entry['mean_top_1_true_alerts'] = float(np.mean([s['top_1']['true_alerts'] for s in entry['seeds'].values()]))
        entry['mean_top_1_false_alerts'] = float(np.mean([s['top_1']['false_alerts'] for s in entry['seeds'].values()]))
        entry['mean_f1'] = float(np.mean([s['f1'] for s in entry['seeds'].values()]))
        results.append(entry)
        print(f"Completed {index+1}/{len(candidates)} candidates ({3*(index+1)} fits)", flush=True)
    exclusive_json(report/'search.json', {'candidates': results, 'fits': len(results)*len(config['model_seeds']),
                                         'search_seed': config['search_seed']})
    winner = select_candidate(results, partition='validation', minimum_recall=config['selection']['minimum_mean_recall'])
    selected = {}; validation_results = {}; fp_results = {}
    for seed in config['model_seeds']:
        name = f'tuned-{seed}'
        source = run/winner['candidate']/f'iforest-{seed}'
        shutil.copytree(source, run/name)
        selected[name] = {'path': name, 'budget_cutoffs': winner['seeds'][str(seed)]['budget_cutoffs']}
    for baseline_name in original['artifacts']:
        name = f'baseline-{baseline_name}'
        # Copy only frozen artifact files, never prior test scores or plots.
        (run/name).mkdir()
        for filename in ('pipeline.joblib', 'threshold.json', 'manifest.json'):
            shutil.copyfile(root/config['baseline_run']/baseline_name/filename, run/name/filename)
        model, _, _ = load_artifact(run/name)
        selected[name] = {'path': name, 'budget_cutoffs': budget_thresholds(risk_scores(model, validation), ids, budgets, partition='validation')}
    for name, spec in selected.items():
        model, threshold, _ = load_artifact(run/spec['path'])
        scores = risk_scores(model, validation)
        validation_results[name] = operating_metrics(scores, y, categories, ids, threshold['threshold'], spec['budget_cutoffs'], budgets, groups)
        fp_results[name] = false_positive_summary(validation, partitions['validation'][0], ids, scores, y,
                    threshold['threshold'], budgets, config['activity_window_seconds'], partition='validation')
    exclusive_json(report/'validation.json', {'population': 'reused validation seed 202', 'models': validation_results,
                  'selected_parameters': winner['parameters'], 'seed_summary': seed_summary([validation_results[f'tuned-{s}'] for s in config['model_seeds']]),
                  'operating_seed_summary': {kind: operating_seed_summary([validation_results[f'{kind}{s}'] for s in config['model_seeds']]) for kind in ('tuned-', 'baseline-iforest-')}})
    exclusive_json(report/'false_positives.json', fp_results)
    exclusive_json(report/'selection.json', {'selected': winner, 'feasibility_is_not_detection_adequacy': True,
                  'selection_partition': 'validation', 'fit_count': 36, 'total_seconds': time.perf_counter()-started})
    inventory = {str(p.relative_to(run)).replace('\\', '/'): digest(p) for p in run.rglob('*') if p.is_file()}
    frozen = {'status': 'frozen', 'config': config, 'baseline_config': baseline, 'corpus_manifest': manifest,
              'baseline_frozen_sha256': digest(root/config['baseline_run']/'frozen.json'),
              'selected_parameters': winner['parameters'], 'models': selected,
              'files': inventory, 'report_files': {p.name: digest(p) for p in report.glob('*.json')},
              'environment': environment(), 'provenance': provenance}
    exclusive_json(run/'frozen.json', frozen)
    exclusive_json(run/'seal.json', {'frozen_sha256': digest(run/'frozen.json')})
    exclusive_json(report/'freeze.json', {'frozen_sha256': digest(run/'frozen.json'), 'config': config,
                                        'selected_parameters': winner['parameters'], 'model_count': len(selected)})
    return {'selected_parameters': winner['parameters'], 'selection': {k: winner[k] for k in winner if k.startswith('mean_')},
            'fits': 36, 'seconds': time.perf_counter()-started}


def verify_tuning(run, root=ROOT):
    run = Path(run); root = Path(root)
    seal = read_json(run/'seal.json')
    if digest(run/'frozen.json') != seal['frozen_sha256']:
        raise ValueError('tuning freeze checksum mismatch')
    frozen = read_json(run/'frozen.json')
    if frozen['status'] != 'frozen' or frozen['environment'] != environment():
        raise ValueError('unfrozen or incompatible experiment')
    validate_tuning(frozen['config'])
    for filename, expected in frozen['files'].items():
        path = (run/filename).resolve()
        if not path.is_relative_to(run.resolve()) or digest(path) != expected:
            raise ValueError('tuning artifact checksum mismatch')
    report = root/frozen['config']['report_dir']
    for filename, expected in frozen['report_files'].items():
        path = (report/filename).resolve()
        if not path.is_relative_to(report.resolve()) or digest(path) != expected:
            raise ValueError('tuning report checksum mismatch')
    # Final execution must use the code frozen before fresh data existed.
    for filename, expected in frozen['provenance']['source_hashes'].items():
        if digest(ROOT/filename) != expected:
            raise ValueError('source changed after tuning freeze')
    return frozen


def audit_final(partitions, final_tx, final_groups):
    """Reuse baseline pair audit with renamed scopes; include historical test."""
    summary = {}
    for name, (tx, groups) in partitions.items():
        # Each pair is audited through the existing three-partition contract using
        # the original train+validation and final, or train+historical+final.
        if name == 'train':
            continue
        remapped = groups.copy()
        for col in ('actor_id', 'scenario_id'):
            remapped[col] = 'validation:' + remapped[col].str.split(':', n=1).str[1]
        remapped['corpus'] = 'validation'
        fg = final_groups.copy()
        for col in ('actor_id', 'scenario_id'):
            fg[col] = 'test:' + fg[col].str.split(':', n=1).str[1]
        fg['corpus'] = 'test'
        summary[name] = audit_partitions({'train': partitions['train'], 'validation': (tx, remapped), 'test': (final_tx, fg)})
    return summary


def generate_final(config, directory):
    # Called only by finalize after verification and one-shot reservation.
    sys.path.insert(0, str(ROOT))
    from scripts.dataset_v2 import BitcoinDatasetV2Generator
    from scripts.prepare_ml_datasets import write_lines
    directory.mkdir(parents=True, exist_ok=False)
    spec = config['final_test']
    generator = BitcoinDatasetV2Generator(spec['seed'], datetime.fromisoformat(spec['start_time']))
    rows = generator.generate(spec['normal'], spec['anomalous'])
    records = [{k: v for k, v in asdict(row).items() if k not in {'label', 'anomaly_type'}} for row in rows]
    groups = [{'txid': row['txid'], 'corpus': 'final', 'actor_id': 'final:'+row['actor_id'],
               'scenario_id': 'final:'+row['scenario_id']} for row in generator.ground_truth]
    truth = [{k: row[k] for k in ('txid', 'label', 'anomaly_type')} for row in generator.ground_truth]
    for suffix, values in (('transactions', records), ('groups', groups), ('labels', truth)):
        write_lines(directory/f'final.{suffix}.jsonl', values)
    manifest = {'corpora': {'final': {'generation': spec, 'records': len(records), 'complete_scenarios': True,
                'files': {p.name: digest(p) for p in directory.glob('*.jsonl')}}}}
    exclusive_json(directory/'manifest.json', manifest)
    return manifest


def finalize(config, root=ROOT):
    started = time.perf_counter(); root = Path(root)
    run = root/config['run_dir']
    frozen = verify_tuning(run, root)
    if frozen['config'] != config:
        raise ValueError('configuration differs from frozen protocol')
    report = root/config['report_dir']; directory = root/config['final_data_dir']
    if directory.exists() or (report/'final_evaluation.json').exists():
        raise FileExistsError('fresh corpus or evaluation already exists')
    # Exclusive reservation: even interrupted attempts cannot silently retry.
    exclusive_json(run/'final_started.json', {'frozen_sha256': digest(run/'frozen.json')})
    baseline = frozen['baseline_config']; data = root/baseline['data_dir']; old_manifest = frozen['corpus_manifest']
    partitions = {name: (read_verified(data, name, 'transactions', old_manifest), read_verified(data, name, 'groups', old_manifest))
                  for name in ('train', 'validation', 'test')}
    models = {name: load_artifact(run/spec['path']) for name, spec in frozen['models'].items()}
    generation_start = time.perf_counter()
    manifest = generate_final(config, directory)
    generation_seconds = time.perf_counter()-generation_start
    tx = read_verified(directory, 'final', 'transactions', manifest)
    groups = read_verified(directory, 'final', 'groups', manifest)
    audit = audit_final(partitions, tx, groups)
    exclusive_json(report/'final_manifest.json', {**manifest, 'split_audit': audit, 'generation_seconds': generation_seconds,
                   'frozen_sha256_before_generation': digest(run/'frozen.json')})
    ids, matrix = from_transactions(tx)
    scenario_ids = groups.set_index('txid').loc[list(ids)].scenario_id.to_numpy()
    scores = {}; score_seconds = {}
    for name, (model, threshold, _) in models.items():
        begin = time.perf_counter(); scores[name] = risk_scores(model, matrix); score_seconds[name] = time.perf_counter()-begin
    score_frame = pd.DataFrame({'txid': ids, **scores})
    score_frame.to_csv(run/'final_scores.csv', index=False, mode='x')
    verify_tuning(run, root)
    # First evaluation truth read, after every model has scored and audit passed.
    y, categories = align_truth(ids, read_verified(directory, 'final', 'labels', manifest))
    results = {name: operating_metrics(values, y, categories, ids, models[name][1]['threshold'],
               frozen['models'][name]['budget_cutoffs'], config['alert_budgets'], scenario_ids) for name, values in scores.items()}
    result = {'population': 'fresh final seed 404 April 2025', 'models': results,
              'selected_parameters': frozen['selected_parameters'], 'final_feature_shape': list(matrix.shape),
              'seed_summary': {kind: seed_summary([results[f'{kind}{seed}'] for seed in config['model_seeds']])
                               for kind in ('tuned-', 'baseline-iforest-')},
              'operating_seed_summary': {kind: operating_seed_summary([results[f'{kind}{seed}'] for seed in config['model_seeds']]) for kind in ('tuned-', 'baseline-iforest-')},
              'frozen_sha256': digest(run/'frozen.json'), 'scores_sha256': digest(run/'final_scores.csv'),
              'generation_seconds': generation_seconds, 'score_seconds': score_seconds,
              'total_seconds': time.perf_counter()-started,
              'interpretation': 'One final evaluation; shared synthetic generator, not deployment accuracy or criminality.'}
    exclusive_json(report/'final_evaluation.json', result)
    exclusive_json(run/'final_completed.json', {'report_sha256': digest(report/'final_evaluation.json')})
    return {'selected_parameters': frozen['selected_parameters'], 'seed_summary': result['seed_summary'], 'seconds': result['total_seconds']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['tune', 'final'])
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = validate_tuning(read_json(args.config))
    print(json.dumps((tune if args.command == 'tune' else finalize)(config), indent=2))


if __name__ == '__main__':
    main()
