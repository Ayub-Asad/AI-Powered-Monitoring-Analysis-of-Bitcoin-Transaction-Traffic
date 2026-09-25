"""Transport-independent upload handling: (filename, bytes) -> (http_status, json_body).

Kept out of ``main.py`` so the status-code logic can be unit-tested without a
web framework, and reused by any other front end (CLI, background job, ...).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from .ingestion import Code, ingest_bytes
from .ingestion.report import IngestionReport

MAX_UPLOAD_BYTES = int(float(os.environ.get("MAX_UPLOAD_MB", "100")) * 1024 * 1024)

_FILE_ERROR_STATUS = {
    Code.UNSUPPORTED_FORMAT: 415,
    Code.FILE_TOO_LARGE: 413,
}


def process_upload(
    filename: str,
    data: bytes,
    fmt: Optional[str] = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> Tuple[int, Dict[str, Any]]:
    """200 = at least one valid row (inspect ``status``/``summary`` for rejects);
    413 too large; 415 unsupported format; 422 nothing usable in the file."""
    if len(data) > max_bytes:
        report = IngestionReport.failed(
            filename, Code.FILE_TOO_LARGE, f"upload is {len(data)} bytes; limit is {max_bytes} bytes"
        )
        report.finalize_status()
        return 413, report.to_dict()

    report = ingest_bytes(data, filename=filename, fmt=fmt).report
    if report.file_errors:
        return _FILE_ERROR_STATUS.get(report.file_errors[0].code, 422), report.to_dict()
    if report.valid_rows == 0:
        return 422, report.to_dict()
    return 200, report.to_dict()
