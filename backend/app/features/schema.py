"""Explicit feature roles. Identifiers and context are never selected numerically."""
from dataclasses import dataclass
import math
import numpy as np

BURST_WINDOW_SECONDS = 60
TRANSACTION_ML_FEATURES = (
    "amount_btc", "fee_btc", "fee_rate_sat_vb", "num_inputs", "num_outputs",
    "fee_to_amount_ratio", "input_output_count_ratio", "hour_of_day_utc", "day_of_week_utc", "is_night_utc",
)
WALLET_ML_FEATURES = (
    "transaction_count", "incoming_transaction_count", "outgoing_transaction_count",
    "total_received_btc", "total_sent_btc", "average_transaction_amount", "median_transaction_amount",
    "transaction_amount_std", "min_transaction_amount", "max_transaction_amount", "unique_counterparties",
    "fan_in", "fan_out", "active_duration_seconds", "mean_inter_transaction_seconds",
    "median_inter_transaction_seconds", "max_tx_in_60s",
)
WALLET_AVAILABILITY_FIELDS = ("incoming_amounts_available", "outgoing_amounts_available")
WALLET_EXTRA_BEHAVIOURAL_FEATURES = ("max_tx_in_window",)
WALLET_CONTEXT_FEATURES = ("unique_observed_src_ips", "unique_observed_dst_ips",
                           "unique_observed_countries", "unique_observed_asns")
TRANSACTION_CONTEXT_FIELDS = ("timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "country", "asn", "asn_org", "source_row")
IDENTIFIERS = {"transaction_features": ("txid",), "wallet_features": ("wallet_address",),
               "transaction_context": ("txid",), "wallet_context": ("wallet_address",)}
UNAVAILABLE_FOR_LEGACY = ("total_received_btc", "total_sent_btc")
ESTIMATED_FEATURES = ()  # No estimated flows are produced.
FORBIDDEN_FIELDS = frozenset({"label", "anomaly_type", "ground_truth", "actor_id", "scenario_id"})


@dataclass(frozen=True)
class FeatureConfig:
    burst_window_seconds: float = BURST_WINDOW_SECONDS

    def __post_init__(self):
        if isinstance(self.burst_window_seconds, bool) or not math.isfinite(self.burst_window_seconds) or self.burst_window_seconds <= 0:
            raise ValueError("burst_window_seconds must be finite and positive")


def ml_ready_frame(table, kind):
    """Explicit numeric selection; missing values require a downstream policy."""
    names = {"transaction": TRANSACTION_ML_FEATURES, "wallet": WALLET_ML_FEATURES}[kind]
    selected = table.loc[:, list(names)].astype(float)
    if not np.isfinite(selected.to_numpy()).all():
        raise ValueError("selected features contain unavailable/nonfinite values; choose and document a missing-value policy")
    return selected
