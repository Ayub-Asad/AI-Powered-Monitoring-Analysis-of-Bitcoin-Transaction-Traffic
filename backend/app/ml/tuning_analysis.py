"""Validation diagnostics and explicit threshold/ranking metrics for tuning."""
import math
import numpy as np
import pandas as pd
from .schema import FEATURES
from .thresholds import binary_labels, validate_scores
from .evaluation import evaluate


def rank_order(scores, ids):
    scores = validate_scores(scores)
    ids = np.asarray(ids, dtype=str)
    if ids.shape != scores.shape or len(set(ids)) != len(ids):
        raise ValueError('ranking requires unique aligned TXIDs')
    return np.lexsort((ids, -scores))


def decision_metrics(predicted, labels):
    p = np.asarray(predicted, dtype=bool)
    y = binary_labels(labels, len(p))
    tp, fp, fn, tn = map(int, ((p & y).sum(), (p & ~y).sum(), (~p & y).sum(), (~p & ~y).sum()))
    return {'alerts': tp + fp, 'true_alerts': tp, 'false_alerts': fp,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            'false_positive_rate': fp / (fp + tn) if fp + tn else None,
            'false_alerts_per_1000_normal': 1000 * fp / (fp + tn) if fp + tn else None,
            'confusion_matrix': {'tn': tn, 'fp': fp, 'fn': fn, 'tp': tp}}


def budget_thresholds(scores, ids, budgets, *, partition):
    if partition != 'validation':
        raise ValueError('cutoffs require validation')
    scores = validate_scores(scores)
    order = rank_order(scores, ids)
    if not len(scores):
        raise ValueError('empty validation scores')
    result = {}
    for budget in budgets:
        if not 0 < budget <= 1:
            raise ValueError('invalid budget')
        result[f'{budget:.0%}'] = float(scores[order[math.ceil(budget * len(scores)) - 1]])
    return result


def operating_metrics(scores, labels, categories, ids, f1_threshold, cutoffs, budgets, groups=None):
    scores = validate_scores(scores)
    y = binary_labels(labels, len(scores))
    order = rank_order(scores, ids)
    result = evaluate(scores, y, categories, ids, f1_threshold, budgets, groups)
    result.pop('alert_budgets')
    result['threshold_operating_points'] = {}
    for name, cutoff in {'f1': f1_threshold, **{f'validation_top_{k}': v for k, v in cutoffs.items()}}.items():
        result['threshold_operating_points'][name] = {'threshold': cutoff, 'operator': '>=', **decision_metrics(scores >= cutoff, y)}
    result['exact_review_budgets'] = {}
    for budget in budgets:
        if not 0 < budget <= 1:
            raise ValueError('invalid budget')
        pred = np.zeros(len(scores), dtype=bool)
        pred[order[:math.ceil(budget * len(scores))]] = True
        result['exact_review_budgets'][f'{budget:.0%}'] = decision_metrics(pred, y)
    return result


def historical_intensity(transactions, ids, window_seconds=60):
    """Global prior count on [t-window,t); tied timestamps never see each other."""
    if window_seconds <= 0:
        raise ValueError('positive window required')
    tx = transactions.sort_values(['timestamp', 'txid'])
    if tx.txid.duplicated().any() or set(ids) != set(tx.txid):
        raise ValueError('diagnostic transaction coverage mismatch')
    times = pd.DatetimeIndex(tx.timestamp).as_unit('ns').asi8
    window = int(window_seconds * 1_000_000_000)
    counts = np.searchsorted(times, times, side='left') - np.searchsorted(times, times-window, side='left')
    return pd.Series(counts, index=tx.txid).loc[list(ids)].to_numpy()


def distribution(values):
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    return {'count': len(values), 'missing': int((~np.isfinite(values)).sum()),
            'mean': float(finite.mean()) if len(finite) else None,
            'quantiles': {str(q): float(np.quantile(finite, q)) for q in (0, .25, .5, .75, .95, 1)} if len(finite) else None}


def false_positive_summary(matrix, transactions, ids, scores, labels, threshold, budgets, window_seconds=60, *, partition):
    if partition != 'validation':
        raise ValueError('false-positive analysis is validation-only')
    if list(matrix.columns) != FEATURES or len(matrix) != len(scores):
        raise ValueError('invalid diagnostic feature matrix')
    scores = validate_scores(scores)
    y = binary_labels(labels, len(scores))
    order = rank_order(scores, ids)
    diag = matrix.reset_index(drop=True).copy()
    diag['prior_60s_transactions'] = historical_intensity(transactions, ids, window_seconds)
    diag['anomaly_score'] = scores
    # Quantile edges learned only on validation; equal scores remain in one bin.
    edges = np.unique(np.quantile(scores, [0, .25, .5, .75, .9, .95, .99, 1])) if len(scores) else np.array([])
    quantile_bins = pd.cut(scores, edges, include_lowest=True).astype(str) if len(edges) > 1 else np.repeat('constant', len(scores))
    bins = {
        'amount_btc': pd.cut(diag.amount_btc, [-np.inf, .00004, .01, 1, 5, 50, np.inf]).astype(str),
        'fee_btc': pd.cut(diag.fee_btc, [-np.inf, .000001, .00001, .0001, .001, np.inf]).astype(str),
        'hour_of_day_utc': diag.hour_of_day_utc.astype(str),
        'day_of_week_utc': diag.day_of_week_utc.astype(str),
        'num_inputs': diag.num_inputs.astype(str), 'num_outputs': diag.num_outputs.astype(str),
        'prior_60s_transactions': pd.cut(diag.prior_60s_transactions, [-np.inf, 0, 1, 5, 20, 100, np.inf]).astype(str),
        'score_quantiles': quantile_bins}
    decisions = {'f1_threshold': scores >= threshold}
    for budget in budgets:
        pred = np.zeros(len(scores), dtype=bool)
        pred[order[:math.ceil(len(scores)*budget)]] = True
        decisions[f'exact_top_{budget:.0%}'] = pred
    result = {'partition': partition, 'activity_window_seconds': window_seconds,
              'activity_interval': '[t-window,t), all tied timestamps excluded',
              'score_quantile_edges': edges.tolist(), 'operating_points': {}}
    for name, pred in decisions.items():
        fp, tn = pred & ~y, ~pred & ~y
        grouped = {}
        for column, buckets in bins.items():
            grouped[column] = []
            for bucket in sorted(set(buckets)):
                mask = np.asarray(buckets == bucket) & ~y
                n = int(mask.sum()); count = int((mask & fp).sum())
                grouped[column].append({'bin': bucket, 'normal': n, 'false_positives': count,
                                        'true_negatives': n-count, 'fpr': count/n if n else None})
        examples = []
        for i in [int(i) for i in order if fp[i]][:8]:
            examples.append({'synthetic_example': f'validation-row-{i:05d}',
                             **{col: float(diag.iloc[i][col]) if pd.notna(diag.iloc[i][col]) else None for col in diag}})
        result['operating_points'][name] = {
            **decision_metrics(pred, y), 'groups': grouped,
            'feature_distributions': {col: {'false_positive': distribution(diag.loc[fp, col]),
                                          'true_negative': distribution(diag.loc[tn, col])} for col in diag},
            'examples': examples}
    return result


def operating_seed_summary(results):
    """Seed variation at each operating point; never a confidence interval."""
    output = {}
    for kind in ('threshold_operating_points', 'exact_review_budgets'):
        output[kind] = {}
        for point in results[0][kind]:
            output[kind][point] = {}
            for field in ('precision', 'recall', 'f1', 'false_positive_rate', 'false_alerts_per_1000_normal', 'alerts', 'true_alerts', 'false_alerts'):
                values = [r[kind][point][field] for r in results if r[kind][point][field] is not None]
                output[kind][point][field] = {'mean': float(np.mean(values)), 'std_population': float(np.std(values)), 'seeds_available': len(values)} if values else None
    return output
