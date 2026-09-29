import json
import os
from pathlib import Path

OPENAPI_PATH = Path(__file__).resolve().parents[1] / "openapi.json"
OPENAPI_GENERATION_DEFAULTS = {
    "APP_ENV": "dev",
    "APP_NAME": "Squicrates",
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "8000",
    "CORS_ORIGINS": '["http://localhost:5173"]',
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "postgres",
    "POSTGRES_DB": "postgres",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5432",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "6379",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    "JWT_SECRET_KEY": "ci-only-jwt-secret-key-for-backend-tests",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
    "OPENAI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
}


def main() -> None:
    # OpenAPI generation imports the app but does not need live service credentials.
    for name, value in OPENAPI_GENERATION_DEFAULTS.items():
        os.environ.setdefault(name, value)

    from app.main import app

    specification = app.openapi()
    OPENAPI_PATH.write_text(
        json.dumps(specification, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {OPENAPI_PATH}")


if __name__ == "__main__":
    main()
