from fastapi import FastAPI
from app.routers.public_menu import router as public_menu_router


def test_api_prefixed_public_routes_are_available():
    app = FastAPI()
    app.include_router(public_menu_router)
    app.include_router(public_menu_router, prefix="/api")
    available_routes = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    assert ("POST", "/api/public/orders") in available_routes
    assert ("GET", "/api/public/menu") in available_routes
