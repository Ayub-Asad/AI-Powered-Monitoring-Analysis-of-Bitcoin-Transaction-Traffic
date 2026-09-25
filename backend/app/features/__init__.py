"""Public feature API accepts only an already-ingested canonical transaction frame."""
from dataclasses import dataclass
import pandas as pd
from .schema import FeatureConfig, FORBIDDEN_FIELDS, TRANSACTION_CONTEXT_FIELDS, ml_ready_frame
from .transactions import transaction_features
from .wallets import wallet_features


@dataclass
class FeatureTables:
    transaction_features: pd.DataFrame
    wallet_features: pd.DataFrame
    transaction_context: pd.DataFrame
    wallet_context: pd.DataFrame
    config: FeatureConfig


def extract_features(transactions, config=None):
    if not isinstance(transactions, pd.DataFrame):
        raise TypeError("pass IngestionResult.transactions, not an IngestionResult or raw records")
    if FORBIDDEN_FIELDS.intersection(transactions.columns):
        raise ValueError("feature input contains evaluation-only fields")
    if transactions.txid.duplicated().any():
        raise ValueError("duplicate TXIDs: use ingestion deduplication before feature extraction")
    if not isinstance(transactions.timestamp.dtype, pd.DatetimeTZDtype) or str(transactions.timestamp.dt.tz) != "UTC":
        raise ValueError("canonical timestamps must be timezone-aware UTC")
    config = config or FeatureConfig()
    tx = transaction_features(transactions)
    wallets, wallet_context = wallet_features(transactions, config)
    context = transactions.sort_values(["timestamp", "txid"], kind="stable")[["txid", *TRANSACTION_CONTEXT_FIELDS]].reset_index(drop=True)
    return FeatureTables(tx, wallets, context, wallet_context, config)


__all__ = ["FeatureConfig", "FeatureTables", "extract_features", "ml_ready_frame"]
