from fastapi import APIRouter
from pydantic import BaseModel

from app.services.route_optimizer import optimize_multi_drop, optimize_route

router = APIRouter(prefix="/api/internal", tags=["internal"])


class RoutePayload(BaseModel):
    coordinates: list


class OptimizationJob(BaseModel):
    id: int
    location: list[float]


class OptimizationPayload(BaseModel):
    start_location: list[float]
    jobs: list[OptimizationJob]


@router.post("/test-route")
def test_route(payload: RoutePayload):
    return optimize_route(payload.coordinates)


@router.post("/test-optimization")
def test_optimization(payload: OptimizationPayload):
    optimized_job_ids = optimize_multi_drop(
        start_location=payload.start_location,
        jobs=[job.model_dump() for job in payload.jobs],
    )
    return {"optimized_job_ids": optimized_job_ids}
