import os
from urllib.parse import quote

import httpx

MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")


async def geocode_address(address: str) -> tuple[float | None, float | None]:
    if not MAPBOX_TOKEN or not (address or "").strip():
        return None, None

    encoded_address = quote(address.strip())
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_address}.json"
    params = {
        "access_token": MAPBOX_TOKEN,
        "limit": 1,
        "country": "BR",
    }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url, params=params)
    except httpx.HTTPError:
        return None, None

    if response.status_code != 200:
        return None, None

    data = response.json()
    if not data.get("features"):
        return None, None

    coords = data["features"][0]["geometry"]["coordinates"]
    lng, lat = coords
    return lat, lng
