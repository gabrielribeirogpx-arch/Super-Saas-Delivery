"""Offline payload diagnostic: no credentials, HTTP calls or database access."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.billing_common import BillingError
from app.services.hotmart_projection import project


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError()
        value[key] = item
    return value


def main():
    # Read stdin only; never echo the payload, buyer details or correlation token.
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            print("INVALID: payload_too_large")
            return 1
        body = json.loads(raw, object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        project(body)
    except BillingError as exc:
        print("INVALID: " + str(exc))
        return 1
    except (ValueError, TypeError):
        print("INVALID: invalid_json")
        return 1
    print("VALID SHAPE ONLY: payment, tenant binding and paid period still require worker validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
