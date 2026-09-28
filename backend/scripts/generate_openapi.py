import json
from pathlib import Path

from app.main import app

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> None:
    specification = app.openapi()
    OPENAPI_PATH.write_text(
        json.dumps(specification, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {OPENAPI_PATH}")


if __name__ == "__main__":
    main()
