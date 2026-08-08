"""Best-effort helpers for Dalipay SDK.

TODO: Tanzanian mobile numbers can be ported between networks, so a prefix
does not guarantee the actual carrier. This table is a best-effort guess
from the commonly-allocated TCRA ranges - always let the caller override
it, and consider surfacing the guess to the end user for confirmation
(e.g. "We detected Vodacom M-Pesa for this number - is that right?")
rather than submitting it blind on a real charge.

073 (TTCL) is deliberately left unmapped: the Dalipay API only accepts
Tigo, Airtel, Halopesa, Azampesa, or Mpesa as `provider`, so there is no
valid guess to return for it - callers must pass `provider` explicitly for
073 numbers.
"""

import re
from typing import Optional

from .types import Provider

# First 3 digits after normalizing to 0XXXXXXXXX -> provider.
_PREFIX_TO_PROVIDER: dict[str, Provider] = {
    "074": "Mpesa",
    "075": "Mpesa",
    "076": "Mpesa",
    "079": "Mpesa",
    "078": "Airtel",
    "068": "Airtel",
    "069": "Airtel",
    "071": "Tigo",
    "065": "Tigo",
    "067": "Tigo",
    "062": "Halopesa",
    "061": "Halopesa",
    "077": "Azampesa",
}


def normalize_msisdn(phone_number: str) -> Optional[str]:
    """
    Normalize a Tanzanian phone number to local 0XXXXXXXXX format.

    Accepts "0712345678", "+255712345678", "255712345678", or "712345678".

    Args:
        phone_number: Phone number in any of the common formats

    Returns:
        Normalized "0XXXXXXXXX" string, or None if it doesn't look like a
        valid Tanzanian mobile number.

    Example:
        >>> normalize_msisdn("+255712345678")
        '0712345678'
    """
    digits = re.sub(r"\D", "", phone_number or "")

    if digits.startswith("255") and len(digits) == 12:
        digits = "0" + digits[3:]
    elif len(digits) == 9:
        digits = "0" + digits

    if len(digits) != 10 or not digits.startswith("0"):
        return None

    return digits


def guess_provider(phone_number: str) -> Optional[Provider]:
    """
    Best-effort guess of a mobile money provider from a phone number prefix.

    Numbers can be ported between networks in Tanzania, so this is a
    convenience default, not a guarantee - if you already know the
    provider (e.g. the customer selected it), pass it explicitly instead
    of relying on this.

    Args:
        phone_number: Customer's mobile money number, any common format

    Returns:
        A Provider guess (Tigo, Airtel, Halopesa, Azampesa, Mpesa), or
        None if the number doesn't look valid or the prefix isn't
        recognized (including 073/TTCL, which has no valid API mapping) -
        in which case the caller must pass provider explicitly.

    Example:
        >>> guess_provider("0755660639")
        'Mpesa'
    """
    normalized = normalize_msisdn(phone_number)
    if normalized is None:
        return None
    return _PREFIX_TO_PROVIDER.get(normalized[:3])
