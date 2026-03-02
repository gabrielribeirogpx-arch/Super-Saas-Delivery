from fastapi import APIRouter
from pydantic import BaseModel

from app.services.route_optimizer import optimize_route

router = APIRouter(prefix="/api/internal", tags=["internal"])


class RoutePayload(BaseModel):
    coordinates: list


@router.post("/test-route")
def test_route(payload: RoutePayload):
    return optimize_route(payload.coordinates)
