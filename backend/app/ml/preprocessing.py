"""Train-only median imputation and fixed monotonic skew transforms."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted
from .schema import FEATURES, validate_matrix


class TransactionPreprocessor(TransformerMixin, BaseEstimator):
    def __init__(self, log_features, btc_multiplier=100000000):
        self.log_features = log_features
        self.btc_multiplier = btc_multiplier

    def fit(self, X, y=None):
        if y is not None:
            raise ValueError("labels must not enter preprocessing")
        values = validate_matrix(X)
        if len(values) == 0 or np.isnan(values).all(axis=0).any():
            raise ValueError("empty training data or entirely missing training feature")
        if set(self.log_features) - set(FEATURES) or self.btc_multiplier != 100000000:
            raise ValueError("unsupported transform configuration")
        with np.errstate(over="ignore", invalid="ignore"):
            self.medians_ = np.nanmedian(values, axis=0)
        if not np.isfinite(self.medians_).all():
            raise ValueError("training medians overflowed")
        self.feature_names_in_ = np.asarray(FEATURES, dtype=object)
        self.n_features_in_ = len(FEATURES)
        return self

    def transform(self, X):
        check_is_fitted(self, "medians_")
        values = validate_matrix(X).copy()
        values = np.where(np.isnan(values), self.medians_, values)
        with np.errstate(over="ignore", invalid="ignore"):
            for name in self.log_features:
                i = FEATURES.index(name)
                if name in {"amount_btc", "fee_btc"}:
                    values[:, i] *= self.btc_multiplier
                values[:, i] = np.log1p(values[:, i])
            as_float32 = values.astype(np.float32)
        if not np.isfinite(as_float32).all():
            raise ValueError("nonfinite transformed values or float32 overflow")
        return pd.DataFrame(values, columns=FEATURES, index=X.index)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(FEATURES, dtype=object)
