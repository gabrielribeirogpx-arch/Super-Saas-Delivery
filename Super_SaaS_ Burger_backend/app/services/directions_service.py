import logging
import os
from math import asin, cos, isfinite, radians, sin, sqrt

import httpx

logger = logging.getLogger(__name__)

MAPBOX_ACCESS_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox/driving"
FALLBACK_SPEED_KMH = 30
MAX_FALLBACK_DISTANCE_KM = 100


def is_valid_coord(lat, lng):
    return (
        isinstance(lat, (int, float))
        and isinstance(lng, (int, float))
        and isfinite(lat)
        and isfinite(lng)
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
        logger.warning("directions fallback detected swapped coordinates; correcting lat=%s lng=%s", normalized_lat, normalized_lng)
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
    return max(0, int(round(earth_radius_m * 2 * asin(sqrt(a)))))


def estimate_duration_seconds(distance_meters, speed_kmh=FALLBACK_SPEED_KMH):
    safe_distance_meters = max(0, int(distance_meters or 0))
    safe_speed_kmh = max(1, float(speed_kmh or FALLBACK_SPEED_KMH))
    return max(0, int(round(safe_distance_meters / (safe_speed_kmh * 1000 / 3600))))


async def _fetch_route(origin_lat, origin_lng, dest_lat, dest_lng, timeout):
    if not MAPBOX_ACCESS_TOKEN:
        return None
    origin = normalize_coord(origin_lat, origin_lng)
    destination = normalize_coord(dest_lat, dest_lng)
    if origin is None or destination is None:
        return None
    coordinates = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    params = {
        "access_token": MAPBOX_ACCESS_TOKEN,
        "geometries": "polyline",  # Flutter's decoder expects precision 5.
        "steps": "true",
        "overview": "full",
        "language": "pt-BR",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{DIRECTIONS_URL}/{coordinates}", params=params)
        if response.status_code != 200:
            logger.warning("mapbox directions status_code=%s", response.status_code)
            return None
        data = response.json()
        if data.get("code") != "Ok":
            logger.warning("mapbox directions code=%s", data.get("code"))
            return None
        return (data.get("routes") or [None])[0]
    except (httpx.HTTPError, ValueError, TypeError) as error:
        logger.warning("mapbox directions unavailable: %s", type(error).__name__)
        return None


async def get_route_data(origin_lat, origin_lng, dest_lat, dest_lng):
    route = await _fetch_route(origin_lat, origin_lng, dest_lat, dest_lng, 5)
    if not route:
        return None, None, None
    try:
        return float(route["distance"]), float(route["duration"]), route.get("geometry")
    except (KeyError, TypeError, ValueError):
        return None, None, None


def _maneuver_name(maneuver):
    kind = str(maneuver.get("type") or "").lower()
    modifier = str(maneuver.get("modifier") or "").lower().replace(" ", "-")
    if kind == "roundabout":
        return "roundabout"
    if modifier == "uturn":
        return "uturn-left"
    if modifier in ("left", "right", "slight-left", "slight-right"):
        return f"turn-{modifier}"
    return "straight"


async def get_navigation_route(origin_lat, origin_lng, dest_lat, dest_lng):
    """Return road geometry and the next instruction without exposing the token."""
    route = await _fetch_route(origin_lat, origin_lng, dest_lat, dest_lng, 8)
    if not route or not isinstance(route.get("geometry"), str) or not route["geometry"]:
        return None
    try:
        steps = ((route.get("legs") or [])[0].get("steps") or [])
        first = steps[0] if steps else {}
        maneuver = first.get("maneuver") or {}
        return {
            "distance_meters": max(0, int(route["distance"])),
            "duration_seconds": max(0, int(route["duration"])),
            "encoded_polyline": route["geometry"],
            "next_instruction": str(maneuver.get("instruction") or "Siga em direção ao destino").strip(),
            "next_maneuver": _maneuver_name(maneuver),
            "next_step_distance_meters": max(0, int(first.get("distance") or 0)),
        }
    except (IndexError, KeyError, TypeError, ValueError):
        logger.warning("mapbox navigation response invalid", exc_info=True)
        return None


async def get_route_metrics_with_fallback(origin_lat, origin_lng, dest_lat, dest_lng):
    distance_meters, duration_seconds, geometry = await get_route_data(origin_lat, origin_lng, dest_lat, dest_lng)
    if distance_meters is not None and duration_seconds is not None:
        return max(0, int(distance_meters)), max(0, int(duration_seconds)), geometry, "mapbox_directions"

    normalized_origin = normalize_coord(origin_lat, origin_lng)
    normalized_destination = normalize_coord(dest_lat, dest_lng)
    if normalized_origin is None or normalized_destination is None:
        logger.warning("invalid coordinates for fallback distance; origin=%s,%s destination=%s,%s", origin_lat, origin_lng, dest_lat, dest_lng)
        return None, None, None, None
    fallback_distance = haversine_distance_meters(*normalized_origin, *normalized_destination)
    if fallback_distance > MAX_FALLBACK_DISTANCE_KM * 1000:
        logger.warning("unrealistic fallback distance detected distance_meters=%s", fallback_distance)
        return None, None, None, None
    return fallback_distance, estimate_duration_seconds(fallback_distance), None, "haversine"
