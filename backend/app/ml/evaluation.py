"""Evaluation is the sole consumer of labels, apart from validation calibration."""
import math
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, auc
from .schema import CATEGORIES
from .thresholds import validate_scores, binary_labels, flags


def align_truth(ids, truth):
    if set(truth.columns) != {"txid", "label", "anomaly_type"} or truth.txid.duplicated().any():
        raise ValueError("invalid truth schema or duplicate IDs")
    if len(set(ids)) != len(ids) or set(ids) != set(truth.txid):
        raise ValueError("truth coverage mismatch")
    aligned = truth.set_index('txid').loc[list(ids)]
    if not aligned.label.isin(['normal', 'anomalous']).all():
        raise ValueError("unknown evaluation labels")
    categories = aligned.anomaly_type.fillna('')
    y = aligned.label.eq('anomalous').to_numpy()
    if not categories[y].isin(CATEGORIES).all() or not categories[~y].eq('').all():
        raise ValueError("inconsistent anomaly category")
    return y, categories.to_numpy()


def alert_metrics(scores, labels, txids, budgets):
    scores = validate_scores(scores)
    y = binary_labels(labels, len(scores))
    ids = np.asarray(txids, dtype=str)
    if ids.shape != scores.shape or len(set(ids)) != len(ids):
        raise ValueError("alert ranking requires unique aligned IDs")
    order = np.lexsort((ids, -scores))
    result = {}
    for budget in budgets:
        if not 0 < budget <= 1:
            raise ValueError("alert budgets must lie in (0,1]")
        count = math.ceil(len(scores) * budget)
        positives = int(y[order[:count]].sum())
        result[f"{budget:.0%}"] = {"alerts": count, "true_positives": positives,
                                   "precision": positives/count if count else None}
    return result


def evaluate(scores, labels, categories, txids, threshold, budgets, scenario_ids=None):
    scores = validate_scores(scores)
    y = binary_labels(labels, len(scores))
    categories = np.asarray(categories)
    if categories.shape != scores.shape:
        raise ValueError("category coverage mismatch")
    pred = flags(scores, threshold)
    tp, fp, fn, tn = [int(v) for v in ((pred & y).sum(), (pred & ~y).sum(), (~pred & y).sum(), (~pred & ~y).sum())]
    precision = tp/(tp+fp) if tp+fp else None
    recall = tp/(tp+fn) if tp+fn else None
    both = bool(len(y) and y.any() and not y.all())
    ap = pr_auc = roc_auc = None
    if both:
        p, r, _ = precision_recall_curve(y, scores)
        ap, pr_auc, roc_auc = float(average_precision_score(y, scores)), float(auc(r, p)), float(roc_auc_score(y, scores))
    per_category = {}
    for category in CATEGORIES:
        mask = (categories == category) & y
        support = int(mask.sum())
        per_category[category] = {"transactions": support, "detected": int((mask & pred).sum()),
                                  "recall": float(pred[mask].mean()) if support else None,
                                  "scenarios": len(set(np.asarray(scenario_ids)[mask])) if scenario_ids is not None else None}
    distributions = {}
    for name, mask in [('normal', ~y), ('anomalous', y)]:
        distributions[name] = {str(q): float(np.quantile(scores[mask], q)) for q in (0, .25, .5, .75, .95, 1)} if mask.any() else None
    return {"records": len(y), "normal": int((~y).sum()), "anomalous": int(y.sum()), "threshold": float(threshold),
            "precision": precision, "recall": recall, "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            "false_positive_rate": fp/(fp+tn) if fp+tn else None,
            "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            "average_precision": ap, "pr_auc_trapezoidal": pr_auc, "roc_auc": roc_auc,
            "auc_unavailable_reason": None if both else "requires both classes",
            "precision_unavailable_reason": None if tp+fp else "no flagged transactions",
            "recall_unavailable_reason": None if tp+fn else "no positive labels",
            "per_category": per_category, "score_quantiles": distributions,
            "alert_budgets": alert_metrics(scores, y, txids, budgets)}


def seed_summary(results):
    names = ['precision', 'recall', 'f1', 'false_positive_rate', 'average_precision', 'pr_auc_trapezoidal', 'roc_auc']
    return {name: {"mean": float(np.mean(values)), "std_population": float(np.std(values)),
                   "min": float(min(values)), "max": float(max(values))}
            for name in names if (values := [r[name] for r in results if r[name] is not None])}


def save_plots(path, scores, y):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for label, mask in [('normal', ~y), ('anomalous', y)]:
        axes[0].hist(scores[mask], bins=40, alpha=.5, density=True, label=label)
    axes[0].set(xlabel='Anomaly score (higher = more anomalous)', ylabel='Density')
    axes[0].legend()
    if y.any() and not y.all():
        p, r, thresholds = precision_recall_curve(y, scores)
        axes[1].plot(r, p)
        pd.DataFrame({'precision': p, 'recall': r, 'threshold': np.r_[thresholds, np.nan]}).to_csv(path/'precision_recall.csv', index=False)
    axes[1].set(xlabel='Recall', ylabel='Precision', ylim=(0,1))
    fig.tight_layout()
    fig.savefig(path/'evaluation.png', dpi=140)
    plt.close(fig)
