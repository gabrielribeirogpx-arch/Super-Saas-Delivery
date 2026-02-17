import os
from dotenv import load_dotenv

# Carrega o .env da raiz do projeto
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./super_saas.db")
ENV = os.getenv("ENV", "dev")
IS_DEV = ENV.lower() in {"dev", "development", "local"}
DEV_BOOTSTRAP_ALLOW = os.getenv("DEV_BOOTSTRAP_ALLOW", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

META_WA_ACCESS_TOKEN = os.getenv("META_WA_ACCESS_TOKEN", "")
META_WA_PHONE_NUMBER_ID = os.getenv("META_WA_PHONE_NUMBER_ID", "")
META_WA_VERIFY_TOKEN = os.getenv("META_WA_VERIFY_TOKEN", "")
META_API_VERSION = os.getenv("META_API_VERSION", "v19.0")

# CORS
_cors_env = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [origin.strip() for origin in _cors_env.split(",") if origin.strip()]
if not CORS_ORIGINS and IS_DEV:
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# Auth (JWT)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

ADMIN_SESSION_SECRET = os.getenv("ADMIN_SESSION_SECRET", "")
ADMIN_SESSION_MAX_AGE_SECONDS = int(os.getenv("ADMIN_SESSION_MAX_AGE_SECONDS", "604800"))
ADMIN_SESSION_COOKIE_SECURE = os.getenv(
    "ADMIN_SESSION_COOKIE_SECURE",
    "0" if IS_DEV else "1",
).strip().lower() in {"1", "true", "yes", "on"}
ADMIN_SESSION_COOKIE_HTTPONLY = os.getenv(
    "ADMIN_SESSION_COOKIE_HTTPONLY",
    "1",
).strip().lower() in {"1", "true", "yes", "on"}
ADMIN_SESSION_COOKIE_SAMESITE = os.getenv(
    "ADMIN_SESSION_COOKIE_SAMESITE",
    "lax" if IS_DEV else "none",
).strip().lower()
if ADMIN_SESSION_COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    ADMIN_SESSION_COOKIE_SAMESITE = "lax" if IS_DEV else "none"

_cookie_domain_env = os.getenv("ADMIN_SESSION_COOKIE_DOMAIN", "").strip() or os.getenv(
    "COOKIE_DOMAIN", ""
).strip()
if _cookie_domain_env:
    ADMIN_SESSION_COOKIE_DOMAIN = _cookie_domain_env
elif not IS_DEV:
    ADMIN_SESSION_COOKIE_DOMAIN = ".up.railway.app"
else:
    ADMIN_SESSION_COOKIE_DOMAIN = None

# Compat
COOKIE_DOMAIN = ADMIN_SESSION_COOKIE_DOMAIN
