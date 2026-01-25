import difflib
import re
import unicodedata

from app.models.menu_item import MenuItem


def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def search_menu_items(db, tenant_id: int, query: str, limit: int = 3) -> list[tuple[MenuItem, float]]:
    normalized_query = normalize(query)
    if not normalized_query:
        return []

    items = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True))
        .all()
    )
    results: list[tuple[MenuItem, float]] = []
    query_tokens = set(normalized_query.split())

    for item in items:
        normalized_name = normalize(item.name)
        if not normalized_name:
            continue

        score = 0.0
        if normalized_query == normalized_name:
            score = 1.0
        else:
            name_tokens = set(normalized_name.split())
            shared_tokens = query_tokens & name_tokens
            token_overlap = len(shared_tokens) / max(len(name_tokens), len(query_tokens), 1)
            similarity = difflib.SequenceMatcher(None, normalized_query, normalized_name).ratio()
            score = max(token_overlap, similarity * 0.85)

            if normalized_query in normalized_name:
                score = max(score, 0.78)

        if score > 0:
            results.append((item, score))

    results.sort(key=lambda entry: entry[1], reverse=True)
    return results[:limit]


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

    parts = re.split(r"\s*(?:,| e | \+ )\s*", raw_text, flags=re.IGNORECASE)
    results: list[dict] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        match = re.match(r"^(?P<qty>\d+|\w+)\s*x?\s*(?P<name>.+)$", part)
        if match:
            qty_token = match.group("qty")
            qty = _parse_qty(qty_token)
            name = match.group("name").strip()
            if qty and name:
                results.append({"raw_name": name, "qty": qty})
                continue

        results.append({"raw_name": part, "qty": 1})

    return results
