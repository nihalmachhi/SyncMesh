"""Conservative product-name normalization for local duplicate suggestions."""

import re
import unicodedata

_UNIT_PATTERN = re.compile(r"\b(\d+(?:\.\d+)?)\s*(kg|g|mg|l|ml)\b")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_name(name: str) -> str:
    """Fold Unicode, punctuation, whitespace, and common metric units."""
    value = unicodedata.normalize("NFKC", name).casefold()

    def normalize_unit(match: re.Match[str]) -> str:
        quantity = float(match.group(1))
        unit = match.group(2)
        factor = {"kg": 1000, "g": 1, "mg": 0.001, "l": 1000, "ml": 1}[unit]
        base_unit = "g" if unit in {"kg", "g", "mg"} else "ml"
        base_quantity = quantity * factor
        rendered = str(int(base_quantity)) if base_quantity.is_integer() else str(base_quantity)
        return f" {rendered}{base_unit} "

    value = _UNIT_PATTERN.sub(normalize_unit, value)
    value = _PUNCTUATION.sub(" ", value)
    return " ".join(value.split())
