"""Field-level validators / normalisers.

Each function takes one raw value, returns the normalised value, and raises
``FieldError`` (with a stable code and a human-readable message) if the value
is unusable. They are pure and know nothing about files or rows.
"""
from __future__ import annotations

import ipaddress
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple

from .errors import Code, FieldError, short_repr

NULL_TOKENS = frozenset({"", "null", "none", "nan", "n/a", "na", "nil", "-"})

MAX_BTC = 21_000_000.0  # total supply cap: anything above is certainly junk
BITCOIN_GENESIS = datetime(2009, 1, 3, tzinfo=timezone.utc)
FUTURE_TOLERANCE = timedelta(days=1)

_TXID_RE = re.compile(r"[0-9a-f]{64}")
_NUMBER_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_EPOCH_RE = re.compile(r"\d{1,16}(?:\.\d+)?")
_COUNTRY_RE = re.compile(r"[A-Z]{2}")
# Structural (not checksum) address checks: the synthetic data has no valid checksums.
_BECH32_RE = re.compile(r"(?:bc|tb|bcrt)1[02-9ac-hj-np-z]{6,87}")
_BASE58_RE = re.compile(r"[123mn][1-9A-HJ-NP-Za-km-z]{25,34}")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def is_null(value: Any) -> bool:
    """True for None, NaN and common textual null markers."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip().lower() in NULL_TOKENS:
        return True
    return False


def _reject_container(value: Any, code: str, what: str) -> None:
    if isinstance(value, (dict, list, tuple, set)):
        raise FieldError(code, f"{what} must be a single value, got {type(value).__name__}")


def _to_float(value: Any, code: str, what: str) -> float:
    _reject_container(value, code, what)
    if isinstance(value, bool):
        raise FieldError(code, f"{what} must be a number, got boolean")
    try:
        if isinstance(value, (int, float)):
            number = float(value)
        else:
            text = str(value).strip()
            if not _NUMBER_RE.fullmatch(text):
                raise FieldError(code, f"{what} is not a valid number: {short_repr(value)!r}")
            number = float(text)
    except OverflowError:
        raise FieldError(code, f"{what} is too large to represent")
    if not math.isfinite(number):
        raise FieldError(code, f"{what} must be finite, got {short_repr(value)!r}")
    return number


# --------------------------------------------------------------------------
# required-field normalisers
# --------------------------------------------------------------------------

def normalize_txid(value: Any) -> str:
    _reject_container(value, Code.INVALID_TXID, "txid")
    text = str(value).strip().lower()
    if not _TXID_RE.fullmatch(text):
        raise FieldError(
            Code.INVALID_TXID,
            f"txid must be exactly 64 hexadecimal characters (got {len(text)} chars: {short_repr(value)!r})",
        )
    return text


def normalize_ip(value: Any) -> str:
    """Return the canonical text form of an IPv4/IPv6 address."""
    _reject_container(value, Code.INVALID_IP, "IP address")
    text = str(value).strip()
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        raise FieldError(Code.INVALID_IP, f"not a valid IPv4/IPv6 address: {short_repr(value)!r}")
    if ip.is_unspecified or ip.is_multicast:
        raise FieldError(Code.INVALID_IP, f"unspecified/multicast address cannot be a peer: {text!r}")
    return str(ip)


def is_public_ip(ip_text: str) -> bool:
    return ipaddress.ip_address(ip_text).is_global


def normalize_port(value: Any) -> int:
    _reject_container(value, Code.INVALID_PORT, "port")
    if isinstance(value, bool):
        raise FieldError(Code.INVALID_PORT, "port must be an integer, got boolean")
    if isinstance(value, int):
        port = value
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise FieldError(Code.INVALID_PORT, f"port must be a whole number, got {value!r}")
        port = int(value)
    else:
        text = str(value).strip()
        if not re.fullmatch(r"\d{1,6}(?:\.0+)?", text):
            raise FieldError(Code.INVALID_PORT, f"port must be an integer, got {short_repr(value)!r}")
        port = int(float(text))
    if not 1 <= port <= 65535:
        raise FieldError(Code.INVALID_PORT, f"port {port} is outside 1-65535")
    return port


def _from_epoch(number: float) -> datetime:
    if abs(number) >= 1e14:
        raise FieldError(Code.INVALID_TIMESTAMP, f"epoch value {number:g} is too large")
    if abs(number) >= 1e11:  # looks like milliseconds
        number /= 1000.0
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise FieldError(Code.INVALID_TIMESTAMP, f"epoch value {number:g} is not a valid time")


def normalize_timestamp(value: Any) -> Tuple[datetime, bool]:
    """Parse to a timezone-aware UTC datetime.

    Accepts ISO-8601 strings (``Z`` or offsets), datetime objects, and epoch
    seconds/milliseconds (number or numeric string). Returns
    ``(datetime_utc, was_naive)``; naive inputs are assumed to be UTC.
    """
    _reject_container(value, Code.INVALID_TIMESTAMP, "timestamp")
    if isinstance(value, bool):
        raise FieldError(Code.INVALID_TIMESTAMP, "timestamp must not be boolean")

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        parsed = _from_epoch(float(value))
    else:
        text = str(value).strip()
        if _EPOCH_RE.fullmatch(text):
            parsed = _from_epoch(float(text))
        else:
            iso = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
            try:
                parsed = datetime.fromisoformat(iso)
            except ValueError:
                raise FieldError(
                    Code.INVALID_TIMESTAMP,
                    f"not an ISO-8601 timestamp or epoch value: {short_repr(value)!r}",
                )

    was_naive = parsed.tzinfo is None
    parsed = parsed.replace(tzinfo=timezone.utc) if was_naive else parsed.astimezone(timezone.utc)

    if parsed < BITCOIN_GENESIS:
        raise FieldError(Code.OUT_OF_RANGE, f"timestamp {parsed.isoformat()} is before Bitcoin genesis (2009-01-03)")
    if parsed > datetime.now(timezone.utc) + FUTURE_TOLERANCE:
        raise FieldError(Code.OUT_OF_RANGE, f"timestamp {parsed.isoformat()} is in the future")
    return parsed, was_naive


def normalize_amount_btc(value: Any) -> float:
    number = round(_to_float(value, Code.INVALID_NUMBER, "amount_btc"), 8)
    if number <= 0:
        raise FieldError(Code.OUT_OF_RANGE, f"amount_btc must be > 0 (minimum is 1 satoshi = 1e-08), got {short_repr(value)!r}")
    if number > MAX_BTC:
        raise FieldError(Code.OUT_OF_RANGE, f"amount_btc exceeds the 21,000,000 BTC supply cap: {short_repr(value)!r}")
    return number


def normalize_fee_btc(value: Any) -> float:
    number = round(_to_float(value, Code.INVALID_NUMBER, "fee_btc"), 8)
    if number < 0:
        raise FieldError(Code.OUT_OF_RANGE, f"fee_btc must be >= 0, got {short_repr(value)!r}")
    if number > MAX_BTC:
        raise FieldError(Code.OUT_OF_RANGE, f"fee_btc exceeds the 21,000,000 BTC supply cap: {short_repr(value)!r}")
    return number


def normalize_address_list(value: Any) -> List[str]:
    """Pipe-separated string (or an already-parsed list) -> list of addresses.

    Order and repeats are preserved (repeats are meaningful: e.g. a peeling
    chain paying the same address twice). Empty items from stray pipes are
    dropped.
    """
    if isinstance(value, (list, tuple)):
        items = list(value)
    elif isinstance(value, str):
        items = value.split("|")
    else:
        raise FieldError(Code.INVALID_ADDRESS, f"address list must be a '|'-separated string or a list, got {type(value).__name__}")

    addresses: List[str] = []
    for item in items:
        if item is None or (isinstance(item, str) and not item.strip()):
            continue
        if not isinstance(item, str):
            raise FieldError(Code.INVALID_ADDRESS, f"address must be a string, got {type(item).__name__}")
        addr = item.strip()
        if addr.lower().startswith(("bc1", "tb1", "bcrt1")):
            addr = addr.lower()  # bech32 is case-insensitive
            valid = _BECH32_RE.fullmatch(addr) is not None
        else:
            valid = _BASE58_RE.fullmatch(addr) is not None
        if not valid:
            raise FieldError(Code.INVALID_ADDRESS, f"not a recognisable Bitcoin address: {short_repr(item)!r}")
        addresses.append(addr)

    if not addresses:
        raise FieldError(Code.EMPTY_ADDRESS_LIST, "address list contains no addresses")
    return addresses


# --------------------------------------------------------------------------
# optional-field normalisers (failure => warning + null, never a rejection)
# --------------------------------------------------------------------------

def _to_nonneg_int(value: Any, what: str, strip_prefix: Optional[str] = None) -> int:
    _reject_container(value, Code.INVALID_NUMBER, what)
    if isinstance(value, bool):
        raise FieldError(Code.INVALID_NUMBER, f"{what} must be an integer, got boolean")
    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise FieldError(Code.INVALID_NUMBER, f"{what} must be a whole number, got {value!r}")
        number = int(value)
    else:
        text = str(value).strip()
        if strip_prefix and text.upper().startswith(strip_prefix):
            text = text[len(strip_prefix):]
        if not re.fullmatch(r"\d{1,12}(?:\.0+)?", text):
            raise FieldError(Code.INVALID_NUMBER, f"{what} must be a non-negative integer, got {short_repr(value)!r}")
        number = int(float(text))
    if number < 0:
        raise FieldError(Code.OUT_OF_RANGE, f"{what} must be >= 0, got {number}")
    return number


def normalize_count(value: Any) -> int:
    return _to_nonneg_int(value, "count")


def normalize_fee_rate(value: Any) -> float:
    number = _to_float(value, Code.INVALID_NUMBER, "fee_rate_sat_vb")
    if number < 0:
        raise FieldError(Code.OUT_OF_RANGE, f"fee_rate_sat_vb must be >= 0, got {short_repr(value)!r}")
    return number


def normalize_country(value: Any) -> str:
    _reject_container(value, Code.INVALID_NUMBER, "country")
    text = str(value).strip().upper()
    if not _COUNTRY_RE.fullmatch(text):
        raise FieldError(Code.OUT_OF_RANGE, f"country must be an ISO alpha-2 code, got {short_repr(value)!r}")
    return text


def normalize_asn(value: Any) -> int:
    asn = _to_nonneg_int(value, "asn", strip_prefix="AS")  # accepts 15169, "15169", "AS15169"
    if asn > 4_294_967_295:
        raise FieldError(Code.OUT_OF_RANGE, f"asn {asn} exceeds the 32-bit ASN range")
    return asn


def normalize_text(value: Any) -> Optional[str]:
    _reject_container(value, Code.INVALID_NUMBER, "text")
    text = str(value).strip()
    return text or None
