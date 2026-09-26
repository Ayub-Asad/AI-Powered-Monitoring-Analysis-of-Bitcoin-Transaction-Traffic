"""Versioned experiment and strict numerical feature boundary."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from ..features.schema import TRANSACTION_ML_FEATURES, FORBIDDEN_FIELDS
from ..features.transactions import transaction_features

FEATURE_VERSION = "transaction-behaviour-v1"
FEATURES = list(TRANSACTION_ML_FEATURES)
ROOT = Path(__file__).resolve().parents[3]
CATEGORIES = ["rapid_fire_layering", "dust_attack", "high_value_single_hop", "peeling_chain",
              "anomalous_port_usage", "fee_anomaly", "geo_velocity_impossible_travel"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_config(config)


def validate_config(config):
    if config["feature_schema_version"] != FEATURE_VERSION:
        raise ValueError("unsupported feature schema")
    if set(config["corpora"]) != {"train", "validation", "test"} or config["corpora"]["train"]["anomalous"] != 0:
        raise ValueError("baseline requires independent normal-only training")
    if len({c["seed"] for c in config["corpora"].values()}) != 3:
        raise ValueError("corpus seeds must be distinct")
    if config["threshold"] != {"objective": "validation_f1", "tie_break": "lowest_fpr_then_highest_threshold", "operator": ">="}:
        raise ValueError("unsupported threshold policy")
    if config["alert_rounding"] != "ceil" or config["alert_tie_break"] != "txid_ascending":
        raise ValueError("unsupported alert policy")
    if config['model_seeds'] != [42, 43, 44] or config['reference_seed'] != 42:
        raise ValueError('baseline uses fixed seeds 42, 43, 44 with reference 42')
    if config['alert_budgets'] != [.01, .05, .1]:
        raise ValueError('baseline uses fixed 1%, 5%, 10% budgets')
    if config['model'].get('contamination') != 'auto' or 'random_state' in config['model']:
        raise ValueError('external calibration requires auto contamination and explicit seed loop')
    expected_preprocessing = {'missing': 'training_median', 'log1p': ['amount_btc','fee_btc','fee_rate_sat_vb','fee_to_amount_ratio','input_output_count_ratio'],
                              'btc_multiplier': 100000000, 'scaling': 'none'}
    if config['preprocessing'] != expected_preprocessing or config['heuristic'] != {'features': FEATURES[:7], 'zero_iqr_scale': 1.0}:
        raise ValueError('preprocessing/heuristic change requires a new experiment contract')
    for spec in config['corpora'].values():
        if any(isinstance(spec[k], bool) or not isinstance(spec[k], int) or spec[k] < 0 for k in ('seed','normal','anomalous')) or spec['normal'] == 0:
            raise ValueError('invalid generation counts or seed')
        start = pd.Timestamp(spec['start_time'])
        if start.tzinfo is None or start.utcoffset().total_seconds() != 0:
            raise ValueError('generation start times must be UTC')
    return config


def from_transactions(transactions):
    if FORBIDDEN_FIELDS.intersection(transactions.columns):
        raise ValueError("evaluation metadata forbidden in feature input")
    if transactions.txid.duplicated().any():
        raise ValueError("duplicate transaction IDs")
    if not isinstance(transactions.timestamp.dtype, pd.DatetimeTZDtype) or str(transactions.timestamp.dt.tz) != "UTC":
        raise ValueError("timestamps must be canonical UTC")
    table = transaction_features(transactions)
    return table.txid.reset_index(drop=True), table[FEATURES].reset_index(drop=True)


def validate_matrix(frame):
    if not isinstance(frame, pd.DataFrame) or list(frame.columns) != FEATURES:
        raise ValueError("expected exact ordered numerical feature schema")
    if any(not pd.api.types.is_numeric_dtype(t) or pd.api.types.is_bool_dtype(t) for t in frame.dtypes):
        raise ValueError("features must be numeric, not strings or booleans")
    values = frame.to_numpy(dtype=float, na_value=np.nan)
    if np.isinf(values).any():
        raise ValueError("infinite feature values")
    optional = {"fee_rate_sat_vb", "input_output_count_ratio"}
    for i, name in enumerate(FEATURES):
        x = values[:, i]
        if name not in optional and np.isnan(x).any():
            raise ValueError(f"unexpected missing feature: {name}")
        finite = x[np.isfinite(x)]
        if (finite < 0).any() or (name == "amount_btc" and (finite <= 0).any()):
            raise ValueError(f"invalid domain: {name}")
        if name in {"num_inputs", "num_outputs", "hour_of_day_utc", "day_of_week_utc", "is_night_utc"}:
            if (finite != np.floor(finite)).any():
                raise ValueError(f"noninteger feature: {name}")
        upper = {"hour_of_day_utc": 23, "day_of_week_utc": 6, "is_night_utc": 1}.get(name)
        if upper is not None and (finite > upper).any():
            raise ValueError(f"out of range: {name}")
    if len(values) and not np.array_equal(values[:, 9], (values[:, 7] < 6).astype(float)):
        raise ValueError("inconsistent night indicator")
    return values
