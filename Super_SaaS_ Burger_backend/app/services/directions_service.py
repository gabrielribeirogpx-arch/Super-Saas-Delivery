import logging
import os
from math import asin, cos, radians, sin, sqrt

import httpx

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("API_KEY")
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
FALLBACK_SPEED_KMH = 30
MAX_FALLBACK_DISTANCE_KM = 100


def is_valid_coord(lat, lng):
    return (
        isinstance(lat, (int, float))
        and isinstance(lng, (int, float))
        and -90 <= lat <= 90
        and -180 <= lng <= 180
    )


def normalize_coord(lat, lng):
    try:
        normalized_lat = float(lat)
        normalized_lng = float(lng)
    except (TypeError, ValueError):
        return None

    if abs(normalized_lat) > 90 and abs(normalized_lng) <= 90:
        logger.warning(
            "directions fallback detected swapped coordinates; correcting lat=%s lng=%s",
            normalized_lat,
            normalized_lng,
        )
        normalized_lat, normalized_lng = normalized_lng, normalized_lat

    if not is_valid_coord(normalized_lat, normalized_lng):
        return None

    return normalized_lat, normalized_lng


def haversine_distance_meters(origin_lat, origin_lng, dest_lat, dest_lng):
    earth_radius_m = 6_371_000
    lat1 = radians(float(origin_lat))
    lng1 = radians(float(origin_lng))
    lat2 = radians(float(dest_lat))
    lng2 = radians(float(dest_lng))
    delta_lat = lat2 - lat1
    delta_lng = lng2 - lng1
    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lng / 2) ** 2
    c = 2 * asin(sqrt(a))
    return max(0, int(round(earth_radius_m * c)))


def estimate_duration_seconds(distance_meters, speed_kmh=FALLBACK_SPEED_KMH):
    safe_distance_meters = max(0, int(distance_meters or 0))
    safe_speed_kmh = max(1, float(speed_kmh or FALLBACK_SPEED_KMH))
    meters_per_second = safe_speed_kmh * 1000 / 3600
    return max(0, int(round(safe_distance_meters / meters_per_second)))


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
        logger.warning("google directions request failed", exc_info=True)
        return None, None, None

    if response.status_code != 200:
        logger.warning("google directions non-200 response status_code=%s", response.status_code)
        return None, None, None

    data = response.json()
    if data.get("status") != "OK":
        logger.warning("google directions status=%s", data.get("status"))
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


async def get_route_metrics_with_fallback(origin_lat, origin_lng, dest_lat, dest_lng):
    distance_meters, duration_seconds, geometry = await get_route_data(origin_lat, origin_lng, dest_lat, dest_lng)
    if distance_meters is not None and duration_seconds is not None:
        return max(0, int(distance_meters)), max(0, int(duration_seconds)), geometry, "google_directions"

    normalized_origin = normalize_coord(origin_lat, origin_lng)
    normalized_destination = normalize_coord(dest_lat, dest_lng)
    if normalized_origin is None or normalized_destination is None:
        logger.warning(
            "invalid coordinates for fallback distance; origin=%s,%s destination=%s,%s",
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
        )
        return None, None, None, None

    fallback_distance = haversine_distance_meters(*normalized_origin, *normalized_destination)
    if fallback_distance > MAX_FALLBACK_DISTANCE_KM * 1000:
        logger.warning("unrealistic fallback distance detected distance_meters=%s", fallback_distance)
        return None, None, None, None

    fallback_duration = estimate_duration_seconds(fallback_distance, speed_kmh=FALLBACK_SPEED_KMH)
    return fallback_distance, fallback_duration, None, "haversine"
