from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from fastapi.openapi.utils import get_openapi

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ROUTER_FEATURE_FLAGS = {
    "FEATURE_LEGACY_ADMIN": "true",
    "FEATURE_ADMIN_UI": "true",
    "FEATURE_R2_UPLOAD": "true",
}
for flag_name, flag_value in ROUTER_FEATURE_FLAGS.items():
    os.environ[flag_name] = flag_value

from app.main import app

SNAPSHOT_PATH = Path("contracts/openapi_snapshot.json")
CRITICAL_SEGMENTS = ("/auth", "/orders", "/payments", "/inventory", "/reports")


def _sort_schema_properties(schema: dict) -> dict:
    sorted_schema = dict(schema)

    properties = sorted_schema.get("properties")
    if isinstance(properties, dict):
        sorted_schema["properties"] = {
            key: _sort_schema_properties(value) if isinstance(value, dict) else value
            for key, value in sorted(properties.items())
        }

    for key in ("items", "additionalProperties", "not"):
        value = sorted_schema.get(key)
        if isinstance(value, dict):
            sorted_schema[key] = _sort_schema_properties(value)

    for key in ("allOf", "anyOf", "oneOf"):
        value = sorted_schema.get(key)
        if isinstance(value, list):
            sorted_schema[key] = [
                _sort_schema_properties(item) if isinstance(item, dict) else item
                for item in value
            ]

    return sorted_schema


def _build_deterministic_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
    )

    openapi_schema["paths"] = dict(sorted(openapi_schema.get("paths", {}).items()))

    components = openapi_schema.get("components", {})
    schemas = components.get("schemas", {})
    if isinstance(schemas, dict):
        components["schemas"] = {
            key: _sort_schema_properties(value) if isinstance(value, dict) else value
            for key, value in sorted(schemas.items())
        }
    openapi_schema["components"] = components

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = _build_deterministic_openapi


def _critical_paths(spec: dict) -> dict:
    paths = spec.get("paths", {})
    selected: dict[str, dict] = {}
    for path, methods in paths.items():
        if any(segment in path for segment in CRITICAL_SEGMENTS):
            selected[path] = methods
    return {"paths": selected, "components": spec.get("components", {})}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    current = _critical_paths(app.openapi())
    if "--update" in sys.argv:
        SNAPSHOT_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Snapshot updated at {SNAPSHOT_PATH}")
        return 0

    if not SNAPSHOT_PATH.exists():
        print(f"Snapshot file not found: {SNAPSHOT_PATH}")
        return 1

    previous = _load_json(SNAPSHOT_PATH)
    if current != previous:
        print("Critical OpenAPI contract changed. Please review and update snapshot intentionally.")
        return 1

    print("OpenAPI critical contracts unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
