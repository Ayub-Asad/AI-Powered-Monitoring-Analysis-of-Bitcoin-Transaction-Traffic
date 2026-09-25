"""Ingestion orchestration: bytes -> IngestionResult.

    decode -> reader (format-specific) -> column resolution -> row validation
           -> duplicate detection -> canonical DataFrame (+ isolated ground truth)

This module never raises for bad *data*; problems are reported in the
``IngestionReport``. It contains no ML, feature or graph logic.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .errors import Code, FileIssue, ReaderError
from .readers import get_reader
from .report import IngestionReport, schema_section
from .row_validator import RowOutcome, validate_row
from .schema import (
    GROUND_TRUTH_COLUMNS,
    LINEAGE_COLUMN,
    TRANSACTION_COLUMNS,
    resolve_columns,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionConfig:
    max_reported_errors: int = 100     # cap on row errors listed in the report
    max_examples_per_warning: int = 3
    max_duplicate_samples: int = 10


@dataclass
class IngestionResult:
    """What downstream stages consume.

    ``transactions`` is the canonical table (chronological, deduplicated, no
    ground truth). ``ground_truth`` (txid, label, anomaly_type) is provided
    separately, for evaluation only, or None if the file had no such columns.
    """

    report: IngestionReport
    transactions: pd.DataFrame
    ground_truth: Optional[pd.DataFrame] = None


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def ingest_file(path: str, fmt: Optional[str] = None, config: Optional[IngestionConfig] = None) -> IngestionResult:
    with open(path, "rb") as fh:
        data = fh.read()
    return ingest_bytes(data, filename=os.path.basename(path), fmt=fmt, config=config)


def ingest_bytes(
    data: bytes,
    filename: str = "upload",
    fmt: Optional[str] = None,
    config: Optional[IngestionConfig] = None,
) -> IngestionResult:
    cfg = config or IngestionConfig()
    started = time.perf_counter()
    report = IngestionReport(filename=filename, max_reported_errors=cfg.max_reported_errors)
    result = IngestionResult(report, build_transactions_frame([]), None)

    logger.info("Ingesting %r (%d bytes, format=%s)", filename, len(data), fmt or "auto")
    try:
        _run(data, filename, fmt, cfg, result)
    except ReaderError as exc:
        report.file_errors.append(FileIssue(exc.code, exc.message))
        logger.warning("Ingestion of %r failed: [%s] %s", filename, exc.code, exc.message)

    report.finalize_status()
    report.processing_time_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "Ingested %r: status=%s received=%d valid=%d rejected=%d duplicates=%d warnings=%d (%.0f ms)",
        filename, report.status, report.rows_received, report.valid_rows, report.rejected_rows,
        report.duplicate_rows, sum(report.warning_counts.values()), report.processing_time_ms,
    )
    return result


# --------------------------------------------------------------------------
# internals
# --------------------------------------------------------------------------

def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")  # tolerates a BOM (common from Excel exports)
    except UnicodeDecodeError as exc:
        raise ReaderError(Code.UNDECODABLE_FILE, f"file is not valid UTF-8 (invalid byte at offset {exc.start})")


def _run(data: bytes, filename: str, fmt: Optional[str], cfg: IngestionConfig, result: IngestionResult) -> None:
    report = result.report

    reader = get_reader(filename, fmt)
    report.format = reader.name
    read = reader.read(_decode(data))
    report.rows_received = len(read.rows)

    mapping = resolve_columns(read.columns)
    report.schema = schema_section(mapping)  # populated even if we fail below, so the user sees what was found

    if not read.rows:
        raise ReaderError(Code.NO_DATA_ROWS, "file contains a header/structure but no data rows")
    if mapping.collisions:
        detail = "; ".join(f"{canon} <- {raws}" for canon, raws in mapping.collisions.items())
        raise ReaderError(Code.DUPLICATE_COLUMNS, f"multiple columns map to the same field: {detail}")
    if mapping.missing_required:
        raise ReaderError(
            Code.MISSING_REQUIRED_COLUMNS,
            f"missing required column(s): {', '.join(mapping.missing_required)}. "
            f"Detected columns: {', '.join(mapping.detected) or '(none)'}",
        )

    # ---- row validation ---------------------------------------------------
    accepted: List[RowOutcome] = []
    rejected = 0
    for raw in read.rows:
        if raw.error is not None:
            errors = [raw.error]
        else:
            outcome = validate_row(raw.data, raw.row_number, mapping)
            errors = outcome.errors
            if not errors:
                accepted.append(outcome)
        if errors:
            rejected += 1
            for issue in errors:
                report.add_row_error(issue)
                logger.debug("row %d rejected: [%s] %s: %s", issue.row, issue.code, issue.field, issue.message)
    report.rejected_rows = rejected

    # ---- duplicate detection (by txid; first occurrence wins) ----------------
    kept: List[RowOutcome] = []
    first_seen: Dict[str, Tuple[int, tuple]] = {}
    for outcome in accepted:
        rec = outcome.record
        fingerprint = _fingerprint(rec)
        first = first_seen.get(rec["txid"])
        if first is None:
            first_seen[rec["txid"]] = (rec["source_row"], fingerprint)
            kept.append(outcome)
            continue
        kind = "exact" if first[1] == fingerprint else "conflicting"
        report.duplicate_rows += 1
        if kind == "exact":
            report.duplicates_exact += 1
        else:
            report.duplicates_conflicting += 1
        if len(report.duplicate_samples) < cfg.max_duplicate_samples:
            report.duplicate_samples.append(
                {"txid": rec["txid"], "row": rec["source_row"], "first_seen_row": first[0], "kind": kind}
            )
    if report.duplicates_conflicting:
        logger.warning(
            "%d row(s) reuse a txid with DIFFERENT content (first occurrence kept)", report.duplicates_conflicting
        )

    report.valid_rows = len(kept)
    for outcome in kept:  # warnings only count for rows that survive
        for issue in outcome.warnings:
            report.add_warning(issue, cfg.max_examples_per_warning)

    # ---- canonical tables ----------------------------------------------------
    records = [o.record for o in kept]
    result.transactions = build_transactions_frame(records)
    if mapping.ground_truth_to_raw:
        result.ground_truth = build_ground_truth_frame(kept, result.transactions)


def _fingerprint(rec: Dict[str, Any]) -> tuple:
    return tuple(
        (k, tuple(val) if isinstance(val, list) else val)
        for k, val in sorted(rec.items())
        if k != LINEAGE_COLUMN
    )


def build_transactions_frame(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """Canonical table: typed columns, chronological (stable) order."""
    df = pd.DataFrame.from_records(records, columns=list(TRANSACTION_COLUMNS))
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    for col in ("src_port", "dst_port", "num_inputs", "num_outputs", LINEAGE_COLUMN):
        df[col] = df[col].astype("int64")
    for col in ("amount_btc", "fee_btc", "fee_rate_sat_vb"):
        df[col] = df[col].astype("float64")
    df["asn"] = pd.array(df["asn"].tolist(), dtype="Int64")
    df = df.sort_values(["timestamp", LINEAGE_COLUMN], kind="stable").reset_index(drop=True)
    return df


def build_ground_truth_frame(kept: List[RowOutcome], transactions: pd.DataFrame) -> pd.DataFrame:
    """Evaluation-only frame, row-aligned with ``transactions`` (txids are unique after dedupe)."""
    rows = {
        o.record["txid"]: {"label": o.ground_truth.get("label"), "anomaly_type": o.ground_truth.get("anomaly_type")}
        for o in kept
    }
    gt = pd.DataFrame.from_dict(rows, orient="index", columns=["label", "anomaly_type"])
    gt = gt.reindex(transactions["txid"])
    gt.index.name = "txid"
    return gt.reset_index()
