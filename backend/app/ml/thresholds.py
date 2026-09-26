"""External validation-only F1 calibration; >= includes all tied scores."""
import numpy as np


def validate_scores(scores):
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or not np.isfinite(scores).all():
        raise ValueError("scores must be a finite vector")
    return scores


def binary_labels(labels, n):
    labels = np.asarray(labels)
    if labels.shape != (n,) or not np.isin(labels, [0, 1]).all():
        raise ValueError("expected aligned binary evaluation labels")
    return labels.astype(bool)


def flags(scores, threshold):
    if not np.isfinite(threshold):
        raise ValueError("threshold must be finite")
    return validate_scores(scores) >= threshold


def calibrate(scores, labels, *, partition):
    if partition != "validation":
        raise ValueError("threshold calibration is restricted to validation")
    scores = validate_scores(scores)
    y = binary_labels(labels, len(scores))
    if not len(y) or not y.any() or y.all():
        raise ValueError("F1 calibration requires both validation classes")
    order = np.argsort(-scores, kind="stable")
    sorted_scores, sorted_y = scores[order], y[order]
    ends = np.r_[np.flatnonzero(sorted_scores[:-1] != sorted_scores[1:]), len(y)-1]
    tp = np.cumsum(sorted_y)[ends]
    fp = ends + 1 - tp
    fn = y.sum() - tp
    f1 = 2 * tp / (2 * tp + fp + fn)
    fpr = fp / (~y).sum()
    # lexsort's last key is primary: maximum F1, minimum FPR, maximum threshold.
    best = np.lexsort((-sorted_scores[ends], fpr, -f1))[0]
    return {"threshold": float(sorted_scores[ends[best]]), "operator": ">=", "partition": partition,
            "objective": "validation_f1", "validation_f1": float(f1[best]), "validation_fpr": float(fpr[best]),
            "tie_break": "lowest_fpr_then_highest_threshold"}
