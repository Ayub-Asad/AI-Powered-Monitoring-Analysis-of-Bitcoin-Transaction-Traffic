"""Optional inference with an existing trusted frozen artifact; never fit or tune."""
from pathlib import Path
from app.ml.artifacts import load_artifact
from app.ml.scoring import score_transactions
from app.ml.schema import digest, from_transactions


def score_with_artifact(transactions, artifact):
    model, threshold, manifest = load_artifact(artifact)
    txids, matrix = from_transactions(transactions)
    version = f"{Path(artifact).name}:{digest(Path(artifact)/'manifest.json')}"
    return score_transactions(model, matrix, txids, threshold['threshold'], version)
