"""Whole-observation-window wallet aggregates, not causal prediction features."""
from collections import defaultdict
import numpy as np
import pandas as pd
from ..money import to_satoshis, from_satoshis
from .schema import WALLET_ML_FEATURES, WALLET_AVAILABILITY_FIELDS, WALLET_EXTRA_BEHAVIOURAL_FEATURES, WALLET_CONTEXT_FEATURES


def max_in_window(times, seconds):
    """Largest count in a closed window [t-seconds, t], including tied times."""
    left = best = 0
    width = int(seconds * 1_000_000_000)
    for right, t in enumerate(times):
        while t-times[left] > width:
            left += 1
        best = max(best, right-left+1)
    return best


def _state():
    return {"times": [], "amounts": [], "incoming": 0, "outgoing": 0, "received": 0, "sent": 0,
            "incoming_available": True, "outgoing_available": True, "senders": set(), "recipients": set(),
            "src_ips": set(), "dst_ips": set(), "countries": set(), "asns": set()}


def _allocations(addresses, amounts):
    if amounts is None or not isinstance(amounts, list):
        return None
    if len(addresses) != len(amounts):
        raise ValueError("amount/address array length mismatch; ingest records before extracting features")
    result = defaultdict(int)
    for address, amount in zip(addresses, amounts):
        result[address] += to_satoshis(amount)
    return result


def wallet_features(transactions, config):
    states = defaultdict(_state)
    frame = transactions.sort_values(["timestamp", "txid"], kind="stable")
    for row in frame.itertuples(index=False):
        inputs, outputs = set(row.input_addresses), set(row.output_addresses)
        sent = _allocations(row.input_addresses, getattr(row, "input_amounts", None))
        received = _allocations(row.output_addresses, getattr(row, "output_amounts", None))
        for wallet in inputs | outputs:
            s = states[wallet]
            s["times"].append(row.timestamp.value)
            s["amounts"].append(row.amount_btc)
            s["src_ips"].add(row.src_ip)
            s["dst_ips"].add(row.dst_ip)
            if pd.notna(row.country):
                s["countries"].add(row.country)
            if pd.notna(row.asn):
                s["asns"].add(row.asn)
            if wallet in inputs:
                s["outgoing"] += 1
                s["recipients"].update(outputs - {wallet})
                if sent is None:
                    s["outgoing_available"] = False
                else:
                    s["sent"] += sent[wallet]
            if wallet in outputs:
                s["incoming"] += 1
                s["senders"].update(inputs - {wallet})
                if received is None:
                    s["incoming_available"] = False
                else:
                    s["received"] += received[wallet]
    rows, contexts = [], []
    for wallet, s in sorted(states.items()):
        amounts = np.asarray(s["amounts"], dtype=float)
        times = s["times"]
        gaps = np.diff(np.asarray(times, dtype="int64"))/1e9
        rows.append({"wallet_address": wallet, "transaction_count": len(times),
                     "incoming_transaction_count": s["incoming"], "outgoing_transaction_count": s["outgoing"],
                     "total_received_btc": from_satoshis(s["received"]) if s["incoming_available"] else None,
                     "total_sent_btc": from_satoshis(s["sent"]) if s["outgoing_available"] else None,
                     "average_transaction_amount": float(amounts.mean()), "median_transaction_amount": float(np.median(amounts)),
                     "transaction_amount_std": float(amounts.std(ddof=0)), "min_transaction_amount": float(amounts.min()),
                     "max_transaction_amount": float(amounts.max()), "unique_counterparties": len(s["senders"] | s["recipients"]),
                     "fan_in": len(s["senders"]), "fan_out": len(s["recipients"]),
                     "active_duration_seconds": (times[-1]-times[0])/1e9,
                     "mean_inter_transaction_seconds": float(gaps.mean()) if len(gaps) else 0.0,
                     "median_inter_transaction_seconds": float(np.median(gaps)) if len(gaps) else 0.0,
                     "max_tx_in_60s": max_in_window(times, 60),
                     "max_tx_in_window": max_in_window(times, config.burst_window_seconds),
                     "incoming_amounts_available": s["incoming_available"], "outgoing_amounts_available": s["outgoing_available"]})
        contexts.append({"wallet_address": wallet, "unique_observed_src_ips": len(s["src_ips"]),
                         "unique_observed_dst_ips": len(s["dst_ips"]), "unique_observed_countries": len(s["countries"]),
                         "unique_observed_asns": len(s["asns"])})
    columns = ["wallet_address", *WALLET_ML_FEATURES, *WALLET_EXTRA_BEHAVIOURAL_FEATURES, *WALLET_AVAILABILITY_FIELDS]
    result = pd.DataFrame(rows, columns=columns)
    # Stable dtypes also for an empty canonical input.
    integer = {"transaction_count", "incoming_transaction_count", "outgoing_transaction_count", "unique_counterparties",
               "fan_in", "fan_out", "max_tx_in_60s", "max_tx_in_window"}
    for col in columns[1:]:
        result[col] = result[col].astype(bool if col in WALLET_AVAILABILITY_FIELDS else "int64" if col in integer else "float64")
    context = pd.DataFrame(contexts, columns=["wallet_address", *WALLET_CONTEXT_FEATURES])
    for col in WALLET_CONTEXT_FEATURES:
        context[col] = context[col].astype("int64")
    return result, context
