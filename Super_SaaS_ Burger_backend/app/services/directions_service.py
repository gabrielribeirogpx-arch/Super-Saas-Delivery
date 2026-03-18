import os

import httpx

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("API_KEY")
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


async def get_route_data(origin_lat, origin_lng, dest_lat, dest_lng):
    if not GOOGLE_MAPS_API_KEY:
        return None, None, None

    params = {
        "origin": f"{origin_lat},{origin_lng}",
        "destination": f"{dest_lat},{dest_lng}",
        "key": GOOGLE_MAPS_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(DIRECTIONS_URL, params=params)
    except httpx.HTTPError:
        return None, None, None

    if response.status_code != 200:
        return None, None, None

    data = response.json()
    if data.get("status") != "OK":
        return None, None, None

    routes = data.get("routes") or []
    if not routes:
        return None, None, None

    legs = routes[0].get("legs") or []
    if not legs:
        return None, None, None

    leg = legs[0]
    distance = (leg.get("distance") or {}).get("value")
    duration = (leg.get("duration") or {}).get("value")

    try:
        distance = float(distance)
        duration = float(duration)
    except (TypeError, ValueError):
        return None, None, None

    return distance, duration, None
