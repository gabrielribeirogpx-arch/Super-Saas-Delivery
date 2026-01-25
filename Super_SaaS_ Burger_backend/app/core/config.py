import os
from dotenv import load_dotenv

# Carrega o .env da raiz do projeto
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./super_saas.db")

META_WA_ACCESS_TOKEN = os.getenv("META_WA_ACCESS_TOKEN", "")
META_WA_PHONE_NUMBER_ID = os.getenv("META_WA_PHONE_NUMBER_ID", "")
META_WA_VERIFY_TOKEN = os.getenv("META_WA_VERIFY_TOKEN", "")
META_API_VERSION = os.getenv("META_API_VERSION", "v19.0")

# Auth (JWT) - defaults are OK for DEV only
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
