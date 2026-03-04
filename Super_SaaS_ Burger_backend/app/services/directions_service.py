import os

import httpx

MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN")


async def get_route_data(origin_lat, origin_lng, dest_lat, dest_lng):
    if not MAPBOX_TOKEN:
        return None, None, None

    url = (
        "https://api.mapbox.com/directions/v5/mapbox/driving/"
        f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
    )

    params = {
        "access_token": MAPBOX_TOKEN,
        "geometries": "geojson",
        "overview": "full",
    }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url, params=params)
    except httpx.HTTPError:
        return None, None, None

    if response.status_code != 200:
        return None, None, None

    data = response.json()

    if not data.get("routes"):
        return None, None, None

    route = data["routes"][0]

    return route.get("distance"), route.get("duration"), route.get("geometry")
