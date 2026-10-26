import os
from typing import Any

from fastapi import HTTPException

OPENROUTE_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/json"
OPENROUTE_OPTIMIZATION_URL = "https://api.openrouteservice.org/v2/optimization"


def optimize_route(coordinates: list):
    api_key = os.getenv("OPENROUTE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTE_API_KEY is not configured")

    import requests

    response = requests.post(
        OPENROUTE_DIRECTIONS_URL,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        json={"coordinates": coordinates},
        timeout=30,
    )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()


def optimize_multi_drop(start_location: list[float], jobs: list[dict[str, Any]]) -> list:
    api_key = os.getenv("OPENROUTE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTE_API_KEY is not configured")

    import requests

    payload = {
        "jobs": jobs,
        "vehicles": [
            {
                "id": 1,
                "profile": "driving-car",
                "start": start_location,
            }
        ],
    }

    response = requests.post(
        OPENROUTE_OPTIMIZATION_URL,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    routes = data.get("routes") or []
    if not routes:
        return []

    steps = routes[0].get("steps") or []
    return [step.get("id") for step in steps if step.get("type") == "job" and "id" in step]
