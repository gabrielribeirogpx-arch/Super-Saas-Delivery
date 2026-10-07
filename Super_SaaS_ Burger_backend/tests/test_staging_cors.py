"""Staging CORS isolation without changing production's compatibility policy."""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def config(env_name, **overrides):
    env = os.environ.copy()
    env.update(
        ENV=env_name,
        CORS_ORIGINS="https://frontend-staging.example.com",
        ORIGENS_CORS="https://frontend-staging.example.com",
        CORS_ALLOW_ORIGIN_REGEX="",
        PLATFORM_BASE_DOMAINS="staging.example.com",
        PUBLIC_BASE_DOMAIN="staging.example.com",
        BASE_DOMAIN="staging.example.com",
    )
    env.update(overrides)
    code = "from app.core.config import CORS_ORIGINS,CORS_ALLOW_ORIGIN_REGEX; import json; print(json.dumps([CORS_ORIGINS,CORS_ALLOW_ORIGIN_REGEX]))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_staging_uses_only_explicit_origins_and_no_wildcard_regex():
    origins, regex = config("staging")
    assert origins == ["https://frontend-staging.example.com"]
    assert regex is None


def test_staging_without_allowlist_is_closed():
    origins, regex = config("staging", ORIGENS_CORS="", CORS_ORIGINS="")
    assert origins == [] and regex is None


def test_production_compatibility_policy_is_preserved():
    origins, regex = config("production")
    assert "http://localhost:3000" in origins
    assert "https://staging.example.com" in origins
    assert "railway" in regex
