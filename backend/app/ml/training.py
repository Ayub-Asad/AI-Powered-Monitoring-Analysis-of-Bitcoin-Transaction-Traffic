"""Model fitting accepts the numerical matrix only, never truth or metadata."""
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from .preprocessing import TransactionPreprocessor
from .schema import validate_matrix


def fit_model(matrix, config, seed):
    validate_matrix(matrix)
    prep = config["preprocessing"]
    if prep["missing"] != "training_median" or prep["scaling"] != "none":
        raise ValueError("unsupported preprocessing policy")
    pipeline = Pipeline([
        ("preprocessing", TransactionPreprocessor(prep["log1p"], prep["btc_multiplier"])),
        ("forest", IsolationForest(random_state=seed, **config["model"]))])
    return pipeline.fit(matrix)
