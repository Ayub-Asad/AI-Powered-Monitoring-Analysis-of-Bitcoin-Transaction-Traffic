"""Canonical internal transaction schema.

This module is the single source of truth for what an ingested transaction
looks like. Everything downstream (features, ML, graph, API) should depend on
these definitions rather than on the shape of any input file.

Two deliberate separations:

* Ground-truth columns (``label``, ``anomaly_type``) are NOT part of the
  canonical transaction schema. They are split into a separate frame so they
  cannot leak into feature engineering by accident.
* ``source_row`` is lineage metadata (which record of the upload this came
  from). It is not a modelling feature.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dtype: str  # logical dtype, documented in the API response
    required: bool
    description: str


# Column order intentionally matches dataset v1 (minus ground truth).
CANONICAL_FIELDS: Tuple[FieldSpec, ...] = (
    FieldSpec("timestamp", "datetime64[UTC]", True, "Transaction time, timezone-aware UTC"),
    FieldSpec("src_ip", "str", True, "Canonical source IP (IPv4 dotted / IPv6 compressed)"),
    FieldSpec("dst_ip", "str", True, "Canonical destination IP"),
    FieldSpec("src_port", "int64", True, "Source port, 1-65535"),
    FieldSpec("dst_port", "int64", True, "Destination port, 1-65535"),
    FieldSpec("txid", "str", True, "64 lowercase hex chars; unique within a dataset"),
    FieldSpec("input_addresses", "list[str]", True, "Input wallet addresses, order preserved"),
    FieldSpec("output_addresses", "list[str]", True, "Output wallet addresses, order preserved"),
    FieldSpec("num_inputs", "int64", False, "Input count (derived from the list if absent)"),
    FieldSpec("num_outputs", "int64", False, "Output count (derived from the list if absent)"),
    FieldSpec("amount_btc", "float64", True, "Total amount in BTC, > 0, 8 dp"),
    FieldSpec("fee_btc", "float64", True, "Miner fee in BTC, >= 0, 8 dp"),
    FieldSpec("fee_rate_sat_vb", "float64", False, "Fee rate sat/vB (NaN if unknown)"),
    FieldSpec("country", "str", False, "ISO-3166 alpha-2 country of src_ip (null if unknown)"),
    FieldSpec("asn", "Int64", False, "Autonomous System Number of src_ip (null if unknown)"),
    FieldSpec("asn_org", "str", False, "ASN organisation name (null if unknown)"),
)

CANONICAL_NAMES: Tuple[str, ...] = tuple(f.name for f in CANONICAL_FIELDS)
REQUIRED_NAMES: Tuple[str, ...] = tuple(f.name for f in CANONICAL_FIELDS if f.required)
OPTIONAL_NAMES: Tuple[str, ...] = tuple(f.name for f in CANONICAL_FIELDS if not f.required)

LINEAGE_COLUMN = "source_row"
TRANSACTION_COLUMNS: Tuple[str, ...] = CANONICAL_NAMES + (LINEAGE_COLUMN,)

# Evaluation-only fields. Never used as model input.
GROUND_TRUTH_NAMES: Tuple[str, ...] = ("label", "anomaly_type")
GROUND_TRUTH_COLUMNS: Tuple[str, ...] = ("txid",) + GROUND_TRUTH_NAMES
VALID_LABELS = ("normal", "anomalous")

# Conservative alias table: only unambiguous names. Keys are already normalised
# (lowercase, non-alphanumerics -> "_"). Extend as real-data sources appear.
COLUMN_ALIASES: Dict[str, str] = {
    "tx_id": "txid",
    "tx_hash": "txid",
    "transaction_id": "txid",
    "transaction_hash": "txid",
    "time": "timestamp",
    "datetime": "timestamp",
    "source_ip": "src_ip",
    "destination_ip": "dst_ip",
    "dest_ip": "dst_ip",
    "source_port": "src_port",
    "destination_port": "dst_port",
    "dest_port": "dst_port",
    "amount": "amount_btc",
    "fee_rate": "fee_rate_sat_vb",
}


def normalize_header(name: str) -> str:
    """'  Tx-ID ' -> 'tx_id'."""
    return re.sub(r"[^0-9a-z]+", "_", str(name).strip().lower()).strip("_")


@dataclass
class ColumnMapping:
    """How the columns found in a file map onto the canonical schema."""

    detected: List[str]
    canonical_to_raw: Dict[str, str] = field(default_factory=dict)
    ground_truth_to_raw: Dict[str, str] = field(default_factory=dict)
    renamed: Dict[str, str] = field(default_factory=dict)  # raw -> canonical
    unrecognized: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    missing_optional: List[str] = field(default_factory=list)
    collisions: Dict[str, List[str]] = field(default_factory=dict)


def resolve_columns(detected: List[str]) -> ColumnMapping:
    mapping = ColumnMapping(detected=list(detected))
    claimed: Dict[str, List[str]] = {}

    for raw in detected:
        key = normalize_header(raw)
        target = COLUMN_ALIASES.get(key, key)
        if target in CANONICAL_NAMES or target in GROUND_TRUTH_NAMES:
            claimed.setdefault(target, []).append(raw)
            if raw != target:
                mapping.renamed[raw] = target
        else:
            mapping.unrecognized.append(raw)

    for target, raws in claimed.items():
        if len(raws) > 1:
            mapping.collisions[target] = raws
            continue
        if target in GROUND_TRUTH_NAMES:
            mapping.ground_truth_to_raw[target] = raws[0]
        else:
            mapping.canonical_to_raw[target] = raws[0]

    mapping.missing_required = [n for n in REQUIRED_NAMES if n not in claimed]
    mapping.missing_optional = [n for n in OPTIONAL_NAMES if n not in claimed]
    return mapping


def describe_canonical_schema() -> List[Dict[str, object]]:
    return [
        {"name": f.name, "dtype": f.dtype, "required": f.required, "description": f.description}
        for f in CANONICAL_FIELDS
    ]
