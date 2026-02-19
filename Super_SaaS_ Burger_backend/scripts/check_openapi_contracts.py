from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app

SNAPSHOT_PATH = Path("contracts/openapi_snapshot.json")
CRITICAL_SEGMENTS = ("/auth", "/orders", "/payments", "/inventory", "/reports")
REF_PATTERN = re.compile(r"^#/components/([^/]+)/([^/]+)$")


def _collect_component_refs(node: Any) -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()

    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            match = REF_PATTERN.match(ref)
            if match:
                refs.add((match.group(1), match.group(2)))

        for value in node.values():
            refs.update(_collect_component_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.update(_collect_component_refs(item))

    return refs


def _collect_security_refs(spec: dict, critical_paths: dict[str, dict]) -> set[tuple[str, str]]:
    refs: set[tuple[str, str]] = set()

    for requirement in spec.get("security", []):
        if not isinstance(requirement, dict):
            continue
        for scheme_name in requirement:
            refs.add(("securitySchemes", scheme_name))

    for methods in critical_paths.values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if not isinstance(operation, dict):
                continue
            for requirement in operation.get("security", []):
                if not isinstance(requirement, dict):
                    continue
                for scheme_name in requirement:
                    refs.add(("securitySchemes", scheme_name))

    return refs


def _select_component_graph(spec: dict, critical_paths: dict[str, dict]) -> dict:
    components = spec.get("components", {})
    pending = _collect_component_refs(critical_paths)
    pending.update(_collect_security_refs(spec, critical_paths))
    selected: dict[str, dict] = {}
    visited: set[tuple[str, str]] = set()

    while pending:
        component_type, component_name = pending.pop()
        key = (component_type, component_name)
        if key in visited:
            continue
        visited.add(key)

        component_group = components.get(component_type)
        if not isinstance(component_group, dict):
            continue
        component_value = component_group.get(component_name)
        if component_value is None:
            continue

        selected.setdefault(component_type, {})[component_name] = component_value
        pending.update(_collect_component_refs(component_value))

    return selected


def _critical_paths(spec: dict) -> dict:
    paths = spec.get("paths", {})
    selected: dict[str, dict] = {}
    for path, methods in paths.items():
        if any(segment in path for segment in CRITICAL_SEGMENTS):
            selected[path] = methods
    return {"paths": selected, "components": _select_component_graph(spec, selected)}


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
