import re
import unicodedata


def normalize_slug(value: str) -> str:
    if not value:
        return ""

    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]", "", value)

    return value
