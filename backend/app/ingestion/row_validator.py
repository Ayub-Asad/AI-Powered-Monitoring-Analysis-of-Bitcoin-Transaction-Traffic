"""Row-level validation: raw record -> canonical record (or a list of errors).

All problems in a row are collected (not just the first) so the user can fix a
file in one pass. Required fields fail the row; optional fields that are
present-but-bad are nulled with a warning. Ground-truth fields never fail a row
and are returned separately from the transaction record.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import validators as v
from ..money import to_satoshis, from_satoshis
from .errors import Code, FieldError, RowIssue, short_repr
from .schema import VALID_LABELS, ColumnMapping

_SIMPLE_REQUIRED = {
    "txid": v.normalize_txid,
    "src_ip": v.normalize_ip,
    "dst_ip": v.normalize_ip,
    "src_port": v.normalize_port,
    "dst_port": v.normalize_port,
    "input_addresses": v.normalize_address_list,
    "output_addresses": v.normalize_address_list,
    "amount_btc": v.normalize_amount_btc,
    "fee_btc": v.normalize_fee_btc,
}
_REQUIRED_ORDER = (
    "timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "txid",
    "input_addresses", "output_addresses", "amount_btc", "fee_btc",
)


@dataclass
class RowOutcome:
    row_number: int
    record: Optional[Dict[str, Any]] = None
    ground_truth: Dict[str, Optional[str]] = field(default_factory=dict)
    errors: List[RowIssue] = field(default_factory=list)
    warnings: List[RowIssue] = field(default_factory=list)


def validate_row(raw: Dict[str, Any], row_number: int, mapping: ColumnMapping) -> RowOutcome:
    out = RowOutcome(row_number)
    rec: Dict[str, Any] = {"source_row": row_number}

    def get(name: str) -> Any:
        raw_name = mapping.canonical_to_raw.get(name)
        return raw.get(raw_name) if raw_name is not None else None

    def error(name: str, code: str, message: str, value: Any = None) -> None:
        out.errors.append(RowIssue(row_number, name, code, message, short_repr(value)))

    def warn(name: str, code: str, message: str, value: Any = None) -> None:
        out.warnings.append(RowIssue(row_number, name, code, message, short_repr(value)))

    is_v2 = any(not v.is_null(get(name)) for name in ("input_amounts", "output_amounts"))

    # ---- required fields ----------------------------------------------------
    for name in _REQUIRED_ORDER:
        value = get(name)
        if v.is_null(value):
            error(name, Code.MISSING_VALUE, f"{name} is required but missing/null")
            continue
        try:
            if name == "timestamp":
                rec[name], was_naive = v.normalize_timestamp(value)
                if was_naive:
                    warn(name, Code.NAIVE_TIMESTAMP_ASSUMED_UTC, "timestamp has no timezone; assumed UTC", value)
            elif is_v2 and name in ("input_addresses", "output_addresses"):
                rec[name] = v.normalize_address_list(value, strict=True)
            else:
                rec[name] = _SIMPLE_REQUIRED[name](value)
        except FieldError as exc:
            error(name, exc.code, exc.message, value)

    if out.errors:
        return out  # rejected: skip optional/ground-truth work and warnings

    # ---- soft checks on valid required fields --------------------------------
    for name in ("src_ip", "dst_ip"):
        if not v.is_public_ip(rec[name]):
            warn(name, Code.NON_PUBLIC_IP, "address is private/loopback/reserved (kept)", rec[name])
    for name in ("input_addresses", "output_addresses"):
        counts = Counter(rec[name])
        if any(c > 1 for c in counts.values()):
            warn(name, Code.DUPLICATE_ADDRESS_IN_LIST, "the same address appears more than once in this list (kept as-is)")

    # ---- optional fields: bad value => warning + null -------------------------
    def optional(name: str, normalizer) -> Any:
        value = get(name)
        if v.is_null(value):
            return None
        try:
            return normalizer(value)
        except FieldError as exc:
            warn(name, Code.INVALID_OPTIONAL_VALUE, f"{exc.message}; stored as null", value)
            return None

    for name, list_field in (("num_inputs", "input_addresses"), ("num_outputs", "output_addresses")):
        if is_v2 and not v.is_null(get(name)):
            try:
                count = v.normalize_count(get(name))
            except FieldError as exc:
                error(name, exc.code, exc.message, get(name))
                count = None
        else:
            count = optional(name, v.normalize_count)
        derived = len(rec[list_field])
        if count is None:
            count = derived
        elif count != derived and is_v2:
            error(name, Code.ARRAY_LENGTH_MISMATCH, "v2 count must match address entries", count)
        elif count != derived:
            warn(name, Code.COUNT_MISMATCH,
                 f"{name}={count} but {list_field} has {derived} entries (source value kept)")
        rec[name] = count

    rec["fee_rate_sat_vb"] = optional("fee_rate_sat_vb", v.normalize_fee_rate)
    rec["country"] = optional("country", v.normalize_country)
    rec["asn"] = optional("asn", v.normalize_asn)
    rec["asn_org"] = optional("asn_org", v.normalize_text)

    # v2 allocations are optional as a pair, but never soft-validated.
    for name in ("input_amounts", "output_amounts"):
        rec[name] = None
        if is_v2:
            try:
                rec[name] = v.normalize_amount_list(get(name))
                address_name = name.replace("amounts", "addresses")
                if len(rec[name]) != len(rec[address_name]):
                    error(name, Code.ARRAY_LENGTH_MISMATCH, "amount/address lengths differ")
            except FieldError as exc:
                error(name, exc.code, exc.message, get(name))
    if is_v2:
        try:
            amount = to_satoshis(get("amount_btc"))
            fee = to_satoshis(get("fee_btc"))
            rec["amount_btc"], rec["fee_btc"] = from_satoshis(amount), from_satoshis(fee)
            if not out.errors:
                inputs = sum(to_satoshis(x) for x in rec["input_amounts"])
                outputs = sum(to_satoshis(x) for x in rec["output_amounts"])
                if inputs != outputs + fee or outputs != amount:
                    error("input_amounts", Code.INCONSISTENT_AMOUNTS,
                          "require input sum = output sum + fee and amount_btc = output sum")
        except ValueError as exc:
            error("amount_btc/fee_btc", Code.INVALID_NUMBER, str(exc))
    if out.errors:
        return out

    # ---- ground truth: isolated, evaluation-only ------------------------------
    for name, raw_name in mapping.ground_truth_to_raw.items():
        value = raw.get(raw_name)
        if v.is_null(value):
            out.ground_truth[name] = None
            continue
        text = str(value).strip()
        if name == "label":
            text = text.lower()
            if text not in VALID_LABELS:
                warn(name, Code.INVALID_OPTIONAL_VALUE, f"label must be one of {list(VALID_LABELS)}; stored as null", value)
                text = None
        out.ground_truth[name] = text or None

    out.record = rec
    return out
