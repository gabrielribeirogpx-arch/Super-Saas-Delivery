from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

_SPECIAL_CHARS_PATTERN = re.compile(r"[^a-z0-9\s-]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_DUPLICATE_HYPHEN_PATTERN = re.compile(r"-+")


def normalize_slug(value: str) -> str:
    """Normalize user-facing names into URL-safe slugs."""
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = _SPECIAL_CHARS_PATTERN.sub("", normalized)
    normalized = _WHITESPACE_PATTERN.sub("-", normalized)
    normalized = _DUPLICATE_HYPHEN_PATTERN.sub("-", normalized)

    return normalized.strip("-")


def build_unique_slug(
    value: str,
    slug_exists: Callable[[str], bool],
    *,
    fallback: str = "loja",
    min_length: int = 3,
    max_length: int = 80,
) -> str:
    """Return the normalized slug or a predictable numeric alternative.

    Conflict alternatives use hyphenated sequential suffixes: base, base-2,
    base-3, ... The base is trimmed so the final slug never exceeds
    ``max_length``.
    """
    base_slug = normalize_slug(value) or fallback
    if len(base_slug) < min_length:
        base_slug = f"{base_slug}{fallback}"
    base_slug = base_slug[:max_length].strip("-") or fallback

    if not slug_exists(base_slug):
        return base_slug

    suffix = 2
    while True:
        suffix_text = f"-{suffix}"
        trimmed_base = base_slug[: max_length - len(suffix_text)].strip("-") or fallback
        candidate = f"{trimmed_base}{suffix_text}"
        if not slug_exists(candidate):
            return candidate
        suffix += 1
