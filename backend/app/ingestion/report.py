"""The structured result of an ingestion run (also the API response body)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .errors import FileIssue, RowIssue
from .schema import ColumnMapping, describe_canonical_schema

STATUS_SUCCESS = "success"  # every row accepted
STATUS_PARTIAL = "partial"  # some rows accepted, some rejected/duplicate
STATUS_FAILED = "failed"    # nothing usable


def schema_section(mapping: Optional[ColumnMapping]) -> Dict[str, Any]:
    section: Dict[str, Any] = {"canonical_schema": describe_canonical_schema()}
    if mapping is None:
        section.update(detected_columns=[])
        return section
    section.update(
        detected_columns=mapping.detected,
        renamed_columns=mapping.renamed,
        unrecognized_columns=mapping.unrecognized,
        missing_required_columns=mapping.missing_required,
        missing_optional_columns=mapping.missing_optional,
        ground_truth_columns=sorted(mapping.ground_truth_to_raw),
        ground_truth_note="Present but isolated from the transaction table; evaluation only, never model input.",
    )
    return section


@dataclass
class IngestionReport:
    filename: str
    format: Optional[str] = None
    status: str = STATUS_FAILED
    rows_received: int = 0
    valid_rows: int = 0
    rejected_rows: int = 0
    duplicate_rows: int = 0
    duplicates_exact: int = 0
    duplicates_conflicting: int = 0
    duplicate_samples: List[Dict[str, Any]] = field(default_factory=list)
    schema: Dict[str, Any] = field(default_factory=lambda: schema_section(None))
    errors: List[RowIssue] = field(default_factory=list)  # capped list of row errors
    total_errors: int = 0
    error_counts: Counter = field(default_factory=Counter)
    file_errors: List[FileIssue] = field(default_factory=list)
    warning_counts: Counter = field(default_factory=Counter)
    warning_examples: Dict[str, List[RowIssue]] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    max_reported_errors: int = 100

    @classmethod
    def failed(cls, filename: str, code: str, message: str, fmt: Optional[str] = None) -> "IngestionReport":
        return cls(filename=filename, format=fmt, file_errors=[FileIssue(code, message)])

    def add_row_error(self, issue: RowIssue) -> None:
        self.total_errors += 1
        self.error_counts[issue.code] += 1
        if len(self.errors) < self.max_reported_errors:
            self.errors.append(issue)

    def add_warning(self, issue: RowIssue, max_examples: int) -> None:
        self.warning_counts[issue.code] += 1
        examples = self.warning_examples.setdefault(issue.code, [])
        if len(examples) < max_examples:
            examples.append(issue)

    def finalize_status(self) -> None:
        if self.file_errors or self.valid_rows == 0:
            self.status = STATUS_FAILED
        elif self.rejected_rows or self.duplicate_rows:
            self.status = STATUS_PARTIAL
        else:
            self.status = STATUS_SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "filename": self.filename,
            "format": self.format,
            "summary": {
                "rows_received": self.rows_received,
                "valid_rows": self.valid_rows,
                "rejected_rows": self.rejected_rows,
                "duplicate_rows": self.duplicate_rows,
            },
            "schema": self.schema,
            "validation_errors": [e.to_dict() for e in self.errors],
            "error_summary": {
                "total_errors": self.total_errors,
                "rows_with_errors": self.rejected_rows,
                "by_code": dict(self.error_counts),
                "truncated": self.total_errors > len(self.errors),
            },
            "file_errors": [e.to_dict() for e in self.file_errors],
            "duplicates": {
                "count": self.duplicate_rows,
                "exact": self.duplicates_exact,
                "conflicting": self.duplicates_conflicting,
                "policy": "first occurrence kept; later rows with the same txid dropped",
                "samples": self.duplicate_samples,
            },
            "warnings": {
                code: {"count": count, "examples": [w.to_dict() for w in self.warning_examples.get(code, [])]}
                for code, count in self.warning_counts.items()
            },
            "processing_time_ms": round(self.processing_time_ms, 1),
        }
