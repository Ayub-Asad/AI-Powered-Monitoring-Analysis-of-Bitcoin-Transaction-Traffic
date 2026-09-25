"""Error codes, issue records and exception types shared by all ingestion modules."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


class Code:
    """Stable, machine-readable issue codes (part of the API contract)."""

    # ---- file-level (nothing usable could be read) -------------------------
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNDECODABLE_FILE = "UNDECODABLE_FILE"
    EMPTY_FILE = "EMPTY_FILE"
    NO_DATA_ROWS = "NO_DATA_ROWS"
    INVALID_JSON = "INVALID_JSON"
    INVALID_STRUCTURE = "INVALID_STRUCTURE"
    DUPLICATE_COLUMNS = "DUPLICATE_COLUMNS"
    MISSING_REQUIRED_COLUMNS = "MISSING_REQUIRED_COLUMNS"

    # ---- row-level errors (row is rejected) --------------------------------
    MALFORMED_ROW = "MALFORMED_ROW"
    MISSING_VALUE = "MISSING_VALUE"
    INVALID_TXID = "INVALID_TXID"
    INVALID_IP = "INVALID_IP"
    INVALID_PORT = "INVALID_PORT"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    INVALID_NUMBER = "INVALID_NUMBER"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    INVALID_ADDRESS = "INVALID_ADDRESS"
    EMPTY_ADDRESS_LIST = "EMPTY_ADDRESS_LIST"

    # ---- row-level warnings (row is kept, value may be nulled) -------------
    NAIVE_TIMESTAMP_ASSUMED_UTC = "NAIVE_TIMESTAMP_ASSUMED_UTC"
    NON_PUBLIC_IP = "NON_PUBLIC_IP"
    COUNT_MISMATCH = "COUNT_MISMATCH"
    DUPLICATE_ADDRESS_IN_LIST = "DUPLICATE_ADDRESS_IN_LIST"
    INVALID_OPTIONAL_VALUE = "INVALID_OPTIONAL_VALUE"


def short_repr(value: Any, limit: int = 80) -> Optional[str]:
    """Bounded string form of an offending value, safe to put in a response."""
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


@dataclass(frozen=True)
class RowIssue:
    """A problem (error or warning) found in one record."""

    row: int  # 1-based record number: header/blank lines are not counted
    field: Optional[str]
    code: str
    message: str
    value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FileIssue:
    code: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FieldError(ValueError):
    """Raised by a field validator when a single value is unusable."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ReaderError(Exception):
    """A file-level problem: the file as a whole cannot be ingested."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class UnsupportedFormatError(ReaderError):
    def __init__(self, message: str):
        super().__init__(Code.UNSUPPORTED_FORMAT, message)
