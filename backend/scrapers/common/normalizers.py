"""Normalization and parsing helpers for future scrapers."""

import math
import re
import unicodedata
from typing import Any


_CHAR_REPLACEMENTS = str.maketrans({
    "'": "",
    "-": " ",
    "’": "",
    "‘": "",
    "–": " ",
    "—": " ",
    "ø": "o",
    "Ø": "O",
    "æ": "ae",
    "Æ": "Ae",
    "œ": "oe",
    "Œ": "Oe",
    "ß": "ss",
    "ł": "l",
    "Ł": "L",
})


def normalize_name(value: Any) -> str:
    """Normalize names for cross-source matching."""
    if value is None:
        return ""
    text = str(value).translate(_CHAR_REPLACEMENTS)
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.lower().split())


def parse_market_value(value: Any) -> float | None:
    """
    Parse a Transfermarkt-style market value into millions of euros.

    Examples:
      "18,00 mill." -> 18.0
      "500 mil"     -> 0.5
      "1.2m"        -> 1.2
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text == "-":
        return None

    text = (
        text.replace("€", "")
        .replace("eur", "")
        .replace(",", ".")
        .strip()
    )

    match = re.search(r"([\d.]+)\s*(mill|mio|m\b)", text)
    if match:
        return round(float(match.group(1)), 2)

    match = re.search(r"([\d.]+)\s*(mil|k\b|tsd)", text)
    if match:
        return round(float(match.group(1)) / 1000, 3)

    match = re.search(r"([\d.]+)", text)
    if match:
        return round(float(match.group(1)), 2)

    return None


def _clean_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except TypeError:
        pass

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-"}:
        return None
    text = text.replace(",", "")

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None

    if math.isnan(number) or math.isinf(number):
        return None
    return number


def safe_int(value: Any) -> int | None:
    """Convert a value to int, returning None for empty/invalid values."""
    number = _clean_number(value)
    return int(round(number)) if number is not None else None


def safe_float(value: Any, decimals: int = 2) -> float | None:
    """Convert a value to float, returning None for empty/invalid values."""
    number = _clean_number(value)
    return round(number, decimals) if number is not None else None


def calculate_per90(value: Any, minutes: Any, decimals: int = 3) -> float | None:
    """Calculate a per-90 metric from a raw value and minutes played."""
    raw_value = _clean_number(value)
    raw_minutes = _clean_number(minutes)
    if raw_value is None or raw_minutes is None or raw_minutes <= 0:
        return None
    return round((raw_value / raw_minutes) * 90, decimals)

