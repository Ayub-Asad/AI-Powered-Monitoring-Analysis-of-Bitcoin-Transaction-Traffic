"""Exact monetary conversion at the schema boundary; no float arithmetic."""
from decimal import Decimal, InvalidOperation

SATOSHIS_PER_BTC = 100_000_000
MAX_SATOSHIS = 21_000_000 * SATOSHIS_PER_BTC


def to_satoshis(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("BTC amount must be a scalar number")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid BTC number") from exc
    if not amount.is_finite() or amount < 0 or amount > 21_000_000:
        raise ValueError("BTC amount must be finite, nonnegative and within the supply cap")
    # Avoid Decimal context rounding concealing sub-satoshi precision.
    sign, digits, exponent = amount.as_tuple()
    coefficient = int(''.join(map(str, digits)))
    if coefficient == 0:
        return 0
    shift = exponent + 8
    if shift < 0:
        if -shift > len(digits):
            raise ValueError("BTC amount must be a whole number of satoshis")
        coefficient, remainder = divmod(coefficient, 10 ** -shift)
        if remainder:
            raise ValueError("BTC amount must be a whole number of satoshis")
        return coefficient
    return coefficient * 10 ** shift


def from_satoshis(value):
    """Float only at the output boundary; amounts are checked in integer units."""
    return value / SATOSHIS_PER_BTC
