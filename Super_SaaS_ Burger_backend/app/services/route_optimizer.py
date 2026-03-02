import os

import requests
from fastapi import HTTPException

OPENROUTE_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/json"


def optimize_route(coordinates: list):
    api_key = os.getenv("OPENROUTE_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTE_API_KEY is not configured")

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
