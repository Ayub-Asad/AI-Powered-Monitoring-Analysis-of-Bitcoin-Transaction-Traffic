"""Predeclared seven-feature robust-deviation comparator."""
import numpy as np
from .schema import FEATURES


class RobustDeviation:
    def __init__(self, preprocessor, features, zero_iqr_scale=1.0):
        self.preprocessor = preprocessor
        self.features = features
        self.zero_iqr_scale = zero_iqr_scale

    def fit(self, matrix):
        if self.features != FEATURES[:7] or self.zero_iqr_scale <= 0:
            raise ValueError("unsupported heuristic configuration")
        values = self.preprocessor.transform(matrix)[self.features].to_numpy()
        self.center_ = np.median(values, axis=0)
        iqr = np.quantile(values, .75, axis=0) - np.quantile(values, .25, axis=0)
        self.scale_ = np.where(iqr == 0, self.zero_iqr_scale, iqr)
        return self

    def score_samples(self, matrix):
        values = self.preprocessor.transform(matrix)[self.features].to_numpy()
        # Match sklearn's normality-score interface; scoring adapter negates it.
        return -np.max(np.abs(values - self.center_) / self.scale_, axis=1)
