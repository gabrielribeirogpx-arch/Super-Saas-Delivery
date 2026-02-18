from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app

SNAPSHOT_PATH = Path("contracts/openapi_snapshot.json")
CRITICAL_SEGMENTS = ("/auth", "/orders", "/payments", "/inventory", "/reports")


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
