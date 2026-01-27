import difflib
import re
import unicodedata

from app.models.menu_item import MenuItem


_ALIAS_PATTERNS = (
    (r"\bcoca\b", "coca cola"),
    (r"\brefri\b", "refrigerante"),
    (r"\bsem\s+acucar\b", "zero"),
    (r"\bzero\b", "zero"),
    (r"\b2\s*l\b", "2 litros"),
    (r"\b2\s*litros?\b", "2 litros"),
)

_GENERIC_TOKENS = {"coca", "refrigerante"}
_STRONG_TOKEN_PHRASES = {"lata", "zero", "2 litros"}


def _apply_aliases(text: str) -> str:
    for pattern, replacement in _ALIAS_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    text = _apply_aliases(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_strong_tokens(tokens: set[str], normalized_text: str) -> set[str]:
    strong: set[str] = set()
    if "lata" in tokens:
        strong.add("lata")
    if "zero" in tokens:
        strong.add("zero")
    if "2" in tokens and "litros" in tokens:
        strong.add("2 litros")
    if "2 litros" in normalized_text:
        strong.add("2 litros")
    return strong


def _score_match(normalized_query: str, normalized_name: str) -> float:
    if not normalized_query or not normalized_name:
        return 0.0

    if normalized_query == normalized_name:
        return 1.0

    query_tokens = set(normalized_query.split())
    name_tokens = set(normalized_name.split())
    if not query_tokens or not name_tokens:
        return 0.0

    shared_tokens = query_tokens & name_tokens
    token_match_ratio = len(shared_tokens) / max(len(query_tokens), 1)
    name_match_ratio = len(shared_tokens) / max(len(name_tokens), 1)
    score = (token_match_ratio * 0.75) + (name_match_ratio * 0.25)

    strong_tokens = _extract_strong_tokens(query_tokens, normalized_query)
    if strong_tokens:
        strong_hits = 0
        for token in strong_tokens:
            if token == "2 litros":
                if "2" in name_tokens and "litros" in name_tokens:
                    strong_hits += 1
            elif token in name_tokens:
                strong_hits += 1
        if strong_hits:
            score += 0.15 * (strong_hits / len(strong_tokens))
        else:
            score *= 0.7

    if len(query_tokens) == 1 and next(iter(query_tokens)) in _GENERIC_TOKENS:
        score *= 0.6

    similarity = difflib.SequenceMatcher(None, normalized_query, normalized_name).ratio()
    score = max(score, similarity * 0.6)

    if normalized_query in normalized_name:
        score = max(score, 0.78)

    return min(score, 1.0)


def _search_menu_items_in_list(
    items: list[MenuItem], query: str, limit: int = 3
) -> list[tuple[MenuItem, float]]:
    normalized_query = normalize(query)
    if not normalized_query:
        return []

    results: list[tuple[MenuItem, float]] = []
    for item in items:
        normalized_name = normalize(item.name)
        if not normalized_name:
            continue

        score = _score_match(normalized_query, normalized_name)
        if score > 0:
            results.append((item, score))

    results.sort(key=lambda entry: entry[1], reverse=True)
    return results[:limit]


def search_menu_items(db, tenant_id: int, query: str, limit: int = 3) -> list[tuple[MenuItem, float]]:
    items = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True))
        .all()
    )
    return _search_menu_items_in_list(items, query, limit=limit)


def search_menu_items_in_candidates(
    items: list[MenuItem], query: str, limit: int = 3
) -> list[tuple[MenuItem, float]]:
    return _search_menu_items_in_list(items, query, limit=limit)


_NUMBER_WORDS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "três": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
}


def _parse_qty(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS.get(token)


def parse_order_text(text: str) -> list[dict]:
    raw_text = text.strip()
    if not raw_text:
        return []

    parts = re.split(r"\s*(?:,|\+)\s*", raw_text, flags=re.IGNORECASE)
    results: list[dict] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        segments = re.split(r"\s+e\s+", part, flags=re.IGNORECASE)
        subparts: list[str] = []
        buffer = ""
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            if not buffer:
                buffer = segment
                continue

            buffer_has_com = re.search(r"\bcom\b|\bc/\b", buffer.lower()) is not None
            segment_match = re.match(r"^(?P<qty>\d+|\w+)\b", segment)
            segment_qty = _parse_qty(segment_match.group("qty")) if segment_match else None
            if buffer_has_com and not segment_qty:
                buffer = f"{buffer} e {segment}"
            else:
                subparts.append(buffer)
                buffer = segment
        if buffer:
            subparts.append(buffer)

        for subpart in subparts:
            subpart = subpart.strip()
            if not subpart:
                continue

            match = re.match(r"^(?P<qty>\d+|\w+)\s*x?\s*(?P<name>.+)$", subpart)
            if match:
                qty_token = match.group("qty")
                qty = _parse_qty(qty_token)
                name = match.group("name").strip()
                if qty and name:
                    results.append({"raw_name": name, "qty": qty})
                    continue

            results.append({"raw_name": subpart, "qty": 1})

    return results
