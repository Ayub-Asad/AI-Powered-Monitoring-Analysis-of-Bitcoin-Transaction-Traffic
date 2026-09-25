"""Format readers: turn file text into raw records. Nothing else.

A reader knows only how to parse one file format into ``(columns, rows)``.
It does no field validation or normalisation; that lives in ``row_validator``.

Adding a format (e.g. XML) means writing one ``BaseReader`` subclass and
calling ``register_reader``; the pipeline, validators and API are untouched.
"""
from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import Code, ReaderError, RowIssue, UnsupportedFormatError


@dataclass
class RawRow:
    """One record as read from the file (or a record-level parse failure)."""

    row_number: int  # 1-based record number; header and blank lines not counted
    data: Optional[Dict[str, Any]]
    error: Optional[RowIssue] = None


@dataclass
class ReadResult:
    columns: List[str]
    rows: List[RawRow]


class BaseReader(ABC):
    name: str = ""
    extensions: tuple = ()

    @abstractmethod
    def read(self, text: str) -> ReadResult:
        """Parse decoded file text. Raise ``ReaderError`` for file-level failures;
        report bad individual records as ``RawRow(error=...)`` instead."""


def _malformed(row_number: int, message: str) -> RawRow:
    return RawRow(row_number, None, RowIssue(row_number, None, Code.MALFORMED_ROW, message))


def _union_columns(records: List[RawRow]) -> List[str]:
    seen: Dict[str, None] = {}
    for rec in records:
        if rec.data:
            for key in rec.data:
                seen.setdefault(str(key), None)
    return list(seen)


class CSVReader(BaseReader):
    name = "csv"
    extensions = (".csv",)

    def read(self, text: str) -> ReadResult:
        reader = iter(csv.reader(io.StringIO(text, newline="")))
        header: Optional[List[str]] = None
        rows: List[RawRow] = []
        number = 0

        while True:
            try:
                fields = next(reader)
            except StopIteration:
                break
            except csv.Error as exc:
                if header is None:
                    raise ReaderError(Code.EMPTY_FILE, f"could not parse CSV header: {exc}")
                number += 1
                rows.append(_malformed(number, f"unparseable CSV record: {exc}"))
                continue

            if not fields or all(not f.strip() for f in fields):
                continue  # blank line
            if header is None:
                header = [f.strip() for f in fields]
                continue

            number += 1
            if len(fields) != len(header):
                rows.append(_malformed(number, f"expected {len(header)} fields but found {len(fields)}"))
            else:
                rows.append(RawRow(number, dict(zip(header, fields))))

        if header is None:
            raise ReaderError(Code.EMPTY_FILE, "file is empty (no CSV header found)")
        return ReadResult(columns=header, rows=rows)


def _rows_from_objects(objects: List[Any]) -> ReadResult:
    rows: List[RawRow] = []
    for i, obj in enumerate(objects, start=1):
        if isinstance(obj, dict):
            rows.append(RawRow(i, obj))
        else:
            rows.append(_malformed(i, f"record must be a JSON object, got {type(obj).__name__}"))
    return ReadResult(columns=_union_columns(rows), rows=rows)


class JSONReader(BaseReader):
    """A JSON array of objects, or ``{"transactions": [...]}``."""

    name = "json"
    extensions = (".json",)
    _WRAPPER_KEYS = ("transactions", "records", "data")

    def read(self, text: str) -> ReadResult:
        if not text.strip():
            raise ReaderError(Code.EMPTY_FILE, "file is empty")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            hint = ""
            if exc.msg.startswith("Extra data"):
                hint = " If this file has one JSON object per line, upload it as .jsonl or pass format=jsonl."
            raise ReaderError(Code.INVALID_JSON, f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}.{hint}")

        if isinstance(doc, dict):
            for key in self._WRAPPER_KEYS:
                if isinstance(doc.get(key), list):
                    doc = doc[key]
                    break
        if not isinstance(doc, list):
            raise ReaderError(
                Code.INVALID_STRUCTURE,
                "JSON must be an array of transaction objects or an object with a "
                f"list under one of {list(self._WRAPPER_KEYS)}",
            )
        return _rows_from_objects(doc)


class JSONLReader(BaseReader):
    """JSON Lines: one JSON object per line."""

    name = "jsonl"
    extensions = (".jsonl", ".ndjson")

    def read(self, text: str) -> ReadResult:
        if not text.strip():
            raise ReaderError(Code.EMPTY_FILE, "file is empty")
        rows: List[RawRow] = []
        number = 0
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            number += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                rows.append(_malformed(number, f"invalid JSON on line {line_no}: {exc.msg}"))
                continue
            if isinstance(obj, dict):
                rows.append(RawRow(number, obj))
            else:
                rows.append(_malformed(number, f"line {line_no} must be a JSON object, got {type(obj).__name__}"))
        return ReadResult(columns=_union_columns(rows), rows=rows)


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

_BY_NAME: Dict[str, BaseReader] = {}
_BY_EXT: Dict[str, BaseReader] = {}


def register_reader(reader: BaseReader) -> None:
    _BY_NAME[reader.name] = reader
    for ext in reader.extensions:
        _BY_EXT[ext.lower()] = reader


def supported_formats() -> List[str]:
    return sorted(_BY_NAME)


def get_reader(filename: str, fmt: Optional[str] = None) -> BaseReader:
    """Pick a reader by explicit ``fmt`` or, failing that, the file extension."""
    if fmt:
        key = fmt.strip().lower().lstrip(".")
        reader = _BY_NAME.get(key) or _BY_EXT.get("." + key)
        if reader is None:
            raise UnsupportedFormatError(f"unknown format {fmt!r}; supported: {', '.join(supported_formats())}")
        return reader
    ext = Path(filename or "").suffix.lower()
    reader = _BY_EXT.get(ext)
    if reader is None:
        raise UnsupportedFormatError(
            f"unsupported file type {ext or '(no extension)'!r}; supported: "
            f"{', '.join(sorted(_BY_EXT))}. Use format=<name> to override."
        )
    return reader


for _reader in (CSVReader(), JSONReader(), JSONLReader()):
    register_reader(_reader)
