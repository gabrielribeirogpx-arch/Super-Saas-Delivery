import pytest
from pydantic import ValidationError

from app.routers.store_theme import StoreThemePayload


def test_store_theme_payload_accepts_valid_values():
    payload = StoreThemePayload(
        primary_color="#112233",
        accent_color="#abcdef",
        background_color="#A1B2C3",
        surface_color="#000000",
        button_radius=12,
        card_radius=24,
        cover_image_url="https://example.com/cover.png",
        logo_url="http://example.com/logo.png",
        hero_overlay_opacity=0.75,
    )

    assert payload.primary_color == "#112233"
    assert payload.button_radius == 12


@pytest.mark.parametrize(
    "field,value",
    [
        ("primary_color", "#123"),
        ("accent_color", "blue"),
        ("background_color", "#12ff"),
    ],
)
def test_store_theme_payload_rejects_invalid_hex(field: str, value: str):
    with pytest.raises(ValidationError):
        StoreThemePayload(**{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("cover_image_url", "ftp://invalid.com/file.png"),
        ("logo_url", "not-a-url"),
    ],
)
def test_store_theme_payload_rejects_invalid_urls(field: str, value: str):
    with pytest.raises(ValidationError):
        StoreThemePayload(**{field: value})


@pytest.mark.parametrize("field,value", [("button_radius", 2), ("card_radius", 40)])
def test_store_theme_payload_rejects_invalid_radius(field: str, value: int):
    with pytest.raises(ValidationError):
        StoreThemePayload(**{field: value})


def test_store_theme_payload_rejects_invalid_overlay():
    with pytest.raises(ValidationError):
        StoreThemePayload(hero_overlay_opacity=1)
