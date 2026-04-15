from __future__ import annotations

INVALID_NORMALIZED_VALUES = {"", "string", "unknown", "none", "unknown_audience"}


def normalize_signal_value(value: object) -> str | None:
    if value is None:
        return None

    normalized = (
        str(value)
        .strip()
        .lower()
        .replace("&", "and")
        .replace("/", "-")
        .replace(" ", "_")
    )

    if normalized in INVALID_NORMALIZED_VALUES:
        return None

    return normalized


def is_valid_signal_key(signal_key: str | None) -> bool:
    if not signal_key:
        return False

    prefix, separator, raw_value = str(signal_key).partition(":")
    if not prefix or not separator:
        return False

    return normalize_signal_value(raw_value) is not None
