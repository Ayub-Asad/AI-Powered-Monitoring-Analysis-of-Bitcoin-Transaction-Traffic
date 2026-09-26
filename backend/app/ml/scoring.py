"""Stable transaction-level outputs; higher score means greater anomaly risk."""
import numpy as np
import pandas as pd
from .schema import FEATURE_VERSION, validate_matrix
from .thresholds import validate_scores, flags


def risk_scores(model, matrix):
    validate_matrix(matrix)
    if len(matrix) == 0:
        return np.array([], dtype=float)
    return validate_scores(-model.score_samples(matrix))


def score_transactions(model, matrix, txids, threshold, model_version):
    txids = pd.Series(txids).reset_index(drop=True)
    if len(txids) != len(matrix) or txids.isna().any() or txids.duplicated().any():
        raise ValueError("IDs must be present, unique and aligned")
    scores = risk_scores(model, matrix)
    return pd.DataFrame({"txid": txids, "anomaly_score": scores, "threshold": threshold,
                         "flagged": flags(scores, threshold), "model_version": model_version,
                         "feature_schema_version": FEATURE_VERSION})
