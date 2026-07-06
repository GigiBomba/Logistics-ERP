"""Convert numeric amounts to their word representation.

Supports English and Romanian, with EUR, RON, USD currencies.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# ── Language-specific number words ────────────────────────────────────────

_EN_ZERO = "zero"
_EN_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_EN_TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
             "sixteen", "seventeen", "eighteen", "nineteen"]
_EN_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
            "eighty", "ninety"]
_EN_SCALE = ["", "thousand", "million"]
_EN_AND = "and"

_RO_ZERO = "zero"
_RO_ONES = ["", "unu", "doi", "trei", "patru", "cinci", "șase", "șapte",
            "opt", "nouă"]
# Feminine forms for 1 and 2 (used with sută/mie)
_RO_ONES_FEM = ["", "o", "două", "trei", "patru", "cinci", "șase", "șapte",
                "opt", "nouă"]
_RO_TEENS = ["zece", "unsprezece", "doisprezece", "treisprezece",
             "paisprezece", "cincisprezece", "șaisprezece", "șaptesprezece",
             "optsprezece", "nouăsprezece"]
_RO_TENS = ["", "", "douăzeci", "treizeci", "patruzeci", "cincizeci",
            "șaizeci", "șaptezeci", "optzeci", "nouăzeci"]
_RO_SCALE = ["", "mie", "milion"]
_RO_SCALE_PLURAL = ["", "mii", "milioane"]
_RO_LINK = "și"

CURRENCY_NAMES: Dict[str, Dict[str, Tuple[str, str, str, str]]] = {
    "en": {
        "EUR": ("euro", "euros", "cent", "cents"),
        "RON": ("leu", "lei", "ban", "bani"),
        "USD": ("dollar", "dollars", "cent", "cents"),
    },
    "ro": {
        "EUR": ("euro", "euro", "cent", "cenți"),
        "RON": ("leu", "lei", "ban", "bani"),
        "USD": ("dolar", "dolari", "cent", "cenți"),
    },
}


def _en_convert_hundreds(n: int) -> str:
    """Convert a number 0-999 to English words."""
    if n == 0:
        return ""
    parts: List[str] = []
    hundreds = n // 100
    remainder = n % 100
    if hundreds > 0:
        parts.append(_EN_ONES[hundreds] + " hundred")
    if remainder > 0:
        if parts:
            parts.append(_EN_AND)
        if remainder < 10:
            parts.append(_EN_ONES[remainder])
        elif remainder < 20:
            parts.append(_EN_TEENS[remainder - 10])
        else:
            tens = remainder // 10
            ones = remainder % 10
            part = _EN_TENS[tens]
            if ones > 0:
                part += "-" + _EN_ONES[ones]
            parts.append(part)
    return " ".join(parts)


def _en_number_to_words(n: int) -> str:
    """Convert an integer 0-999999 to English words."""
    if n == 0:
        return _EN_ZERO
    if n < 0:
        return "negative " + _en_number_to_words(-n)
    parts: List[str] = []
    scale_idx = 0
    while n > 0:
        chunk = n % 1000
        if chunk != 0:
            chunk_words = _en_convert_hundreds(chunk)
            if _EN_SCALE[scale_idx]:
                chunk_words += " " + _EN_SCALE[scale_idx]
            parts.insert(0, chunk_words)
        n //= 1000
        scale_idx += 1
    return " ".join(parts).strip()


def _ro_convert_hundreds(n: int, is_fem: bool = False) -> str:
    """Convert a number 0-999 to Romanian words.

    In Romanian, ``și`` is used only between tens and ones
    (``cincizeci și cinci``), never between hundreds and tens
    (``două sute cincizeci``) or hundreds and ones (``o sută cinci``).
    """
    if n == 0:
        return ""
    parts: List[str] = []
    hundreds = n // 100
    remainder = n % 100

    if hundreds > 0:
        if hundreds == 1:
            parts.append("o sută")
        else:
            parts.append(_RO_ONES_FEM[hundreds] + " sute")

    if remainder > 0:
        if remainder < 10:
            parts.append(_RO_ONES_FEM[remainder] if is_fem and remainder in (1, 2) else _RO_ONES[remainder])
        elif remainder < 20:
            parts.append(_RO_TEENS[remainder - 10])
        else:
            tens = remainder // 10
            ones = remainder % 10
            part = _RO_TENS[tens]
            if ones > 0:
                    part += " " + _RO_LINK + " " + (_RO_ONES_FEM[ones] if is_fem and ones in (1, 2) else _RO_ONES[ones])
            parts.append(part)
    return " ".join(parts)


def _ro_number_to_words(n: int) -> str:
    """Convert an integer 0-999999 to Romanian words."""
    if n == 0:
        return _RO_ZERO
    if n < 0:
        return "minus " + _ro_number_to_words(-n)
    parts: List[str] = []
    scale_idx = 0
    while n > 0:
        chunk = n % 1000
        if chunk != 0:
            is_thousand = scale_idx == 1
            is_million = scale_idx == 2
            if scale_idx == 1 and chunk == 1:
                chunk_words = "o mie"
            elif scale_idx == 1:
                chunk_words = _ro_convert_hundreds(chunk, is_fem=True) + " mii"
            elif scale_idx == 2 and chunk == 1:
                chunk_words = "un milion"
            elif scale_idx == 2:
                chunk_words = _ro_convert_hundreds(chunk) + " milioane"
            else:
                chunk_words = _ro_convert_hundreds(chunk)
            parts.insert(0, chunk_words)
        n //= 1000
        scale_idx += 1
    return " ".join(parts).strip()


def number_to_words(amount: float, currency: str = "EUR", lang: str = "en") -> str:
    """Convert a numeric amount to its word representation.

    Args:
        amount: The numeric amount (e.g. 1250.50).
        currency: ISO currency code (EUR, RON, USD).
        lang: Language code (``"en"`` or ``"ro"``).

    Returns:
        Human-readable amount in words.

    Raises:
        ValueError: If amount is negative.
    """
    if amount < 0:
        raise ValueError("Amount cannot be negative")
    if amount > 9_999_999:
        raise ValueError("Amount exceeds maximum supported value (9,999,999)")

    # Get currency names for the language
    currency_map = CURRENCY_NAMES.get(lang, CURRENCY_NAMES["en"])
    if currency not in currency_map:
        currency = "EUR"
    c_single, c_plural, sub_single, sub_plural = currency_map[currency]

    # Split integer and fractional parts
    integer_part = int(amount)
    fractional_part = round((amount - integer_part) * 100)

    # Convert integer part
    if lang == "ro":
        int_words = _ro_number_to_words(integer_part)
        # Romanian uses "un" (not "unu") before masculine currency nouns
        if integer_part == 1:
            int_words = "un"
    else:
        int_words = _en_number_to_words(integer_part)
    if int_words == _EN_ZERO if lang == "en" else int_words == _RO_ZERO:
        int_words = "zero"
        c_word = c_plural
    elif integer_part == 1:
        c_word = c_single
    else:
        c_word = c_plural

    result = f"{int_words} {c_word}"

    # Convert fractional part
    if fractional_part > 0:
        if lang == "ro":
            sub_words = _ro_number_to_words(fractional_part)
            if fractional_part == 1:
                sub_words = "un"
        else:
            sub_words = _en_number_to_words(fractional_part)
        sub_word = sub_single if fractional_part == 1 else sub_plural
        result += f" {_RO_LINK if lang == 'ro' else _EN_AND} {sub_words} {sub_word}"
    else:
        result += f" {_RO_LINK if lang == 'ro' else _EN_AND} zero {sub_plural}"

    # Capitalize first letter
    return result[0].upper() + result[1:]
