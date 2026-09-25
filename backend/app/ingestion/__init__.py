"""Bitcoin transaction ingestion layer (dataset -> canonical transaction table)."""
from .errors import Code
from .pipeline import IngestionConfig, IngestionResult, ingest_bytes, ingest_file
from .readers import BaseReader, ReadResult, RawRow, register_reader, supported_formats
from .report import IngestionReport
from .schema import (
    CANONICAL_FIELDS,
    CANONICAL_NAMES,
    GROUND_TRUTH_NAMES,
    REQUIRED_NAMES,
    TRANSACTION_COLUMNS,
)

__all__ = [
    "BaseReader", "CANONICAL_FIELDS", "CANONICAL_NAMES", "Code", "GROUND_TRUTH_NAMES",
    "IngestionConfig", "IngestionReport", "IngestionResult", "RawRow", "ReadResult",
    "REQUIRED_NAMES", "TRANSACTION_COLUMNS", "ingest_bytes", "ingest_file",
    "register_reader", "supported_formats",
]
