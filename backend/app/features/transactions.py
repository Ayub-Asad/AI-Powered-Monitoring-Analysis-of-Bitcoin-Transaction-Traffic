"""Per-transaction behavioural features from canonical transactions only."""
import numpy as np
import pandas as pd
from .schema import TRANSACTION_ML_FEATURES


def transaction_features(transactions):
    frame = transactions.sort_values(["timestamp", "txid"], kind="stable")
    result = frame[["txid", "amount_btc", "fee_btc", "fee_rate_sat_vb", "num_inputs", "num_outputs"]].copy()
    result["fee_to_amount_ratio"] = frame.fee_btc / frame.amount_btc
    # Legacy mismatched count fields retain their source meaning, including zero.
    # An undefined ratio is unavailable, not fabricated or infinite.
    result["input_output_count_ratio"] = frame.num_inputs / frame.num_outputs.replace(0, np.nan)
    result["hour_of_day_utc"] = frame.timestamp.dt.hour
    result["day_of_week_utc"] = frame.timestamp.dt.dayofweek
    result["is_night_utc"] = (frame.timestamp.dt.hour < 6).astype("int64")
    return result[["txid", *TRANSACTION_ML_FEATURES]].reset_index(drop=True)
