from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))

    previous_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = f"{ROOT}{os.pathsep}{previous_pythonpath}" if previous_pythonpath else str(ROOT)

    script = ScriptDirectory.from_config(config)
    heads = list(script.get_heads())

    if len(heads) != 1:
        print(f"Expected exactly 1 Alembic head, found {len(heads)}: {', '.join(heads)}")
        return 1

    print(f"Alembic head check passed: {heads[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
