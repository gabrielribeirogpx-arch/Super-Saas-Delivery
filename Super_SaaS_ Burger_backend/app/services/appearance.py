from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

ALLOWED_HERO_MODES = {"minimal", "commercial"}
ALLOWED_BUTTON_STYLES = {"rounded", "square", "pill"}
ALLOWED_LAYOUT_MODES = {"minimal", "commercial", "hybrid"}

DEFAULT_APPEARANCE: dict[str, str] = {
    "primary_color": "#2563eb",
    "secondary_color": "#111827",
    "hero_mode": "commercial",
    "hero_title": "",
    "hero_subtitle": "",
    "logo_url": "",
    "cover_url": "",
    "button_style": "rounded",
    "layout_mode": "hybrid",
}


def parse_theme_json(theme_value: str | None) -> dict[str, Any]:
    if not theme_value:
        return {}

    try:
        parsed = json.loads(theme_value)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, dict):
        return parsed
    return {}


def build_appearance_payload(
    *,
    theme_value: str | None,
    primary_color: str | None,
    logo_url: str | None,
    cover_image_url: str | None,
) -> dict[str, str]:
    payload = deepcopy(DEFAULT_APPEARANCE)
    theme_json = parse_theme_json(theme_value)
    stored = theme_json.get("appearance")

    if isinstance(stored, dict):
        for key in payload:
            value = stored.get(key)
            if isinstance(value, str):
                payload[key] = value

    if not payload["primary_color"] and primary_color:
        payload["primary_color"] = primary_color
    if not payload["logo_url"] and logo_url:
        payload["logo_url"] = logo_url
    if not payload["cover_url"] and cover_image_url:
        payload["cover_url"] = cover_image_url

    if primary_color and HEX_COLOR_PATTERN.match(primary_color.strip()):
        payload["primary_color"] = primary_color.strip()

    return payload


def validate_appearance(payload: dict[str, str]) -> dict[str, str]:
    normalized = deepcopy(DEFAULT_APPEARANCE)

    for key in normalized:
        value = payload.get(key)
        if isinstance(value, str):
            normalized[key] = value.strip()

    if not HEX_COLOR_PATTERN.match(normalized["primary_color"]):
        raise ValueError("primary_color deve ser um HEX válido")
    if not HEX_COLOR_PATTERN.match(normalized["secondary_color"]):
        raise ValueError("secondary_color deve ser um HEX válido")

    if normalized["hero_mode"] not in ALLOWED_HERO_MODES:
        raise ValueError("hero_mode inválido")

    if normalized["button_style"] not in ALLOWED_BUTTON_STYLES:
        raise ValueError("button_style inválido")

    if normalized["layout_mode"] not in ALLOWED_LAYOUT_MODES:
        raise ValueError("layout_mode inválido")

    return normalized


def merge_appearance_into_theme(theme_value: str | None, appearance: dict[str, str]) -> str:
    theme_json = parse_theme_json(theme_value)
    theme_json["appearance"] = appearance
    return json.dumps(theme_json, ensure_ascii=False)
