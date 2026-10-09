import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "dev-secret-key-push-data-manager"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "push_data_manager.db_models",
]

MIDDLEWARE = []

ROOT_URLCONF = "config.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DATABASE_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL;",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

# ATS Sources
ATS_SOURCES = {
    "alpha": {
        "base_url": os.environ.get("ALPHA_BASE_URL", "http://localhost:8001"),
    },
    "beta": {
        "base_url": os.environ.get("BETA_BASE_URL", "http://localhost:8002"),
    },
}

TALENT_POOL_GRPC_TARGET = os.environ.get("TALENT_POOL_GRPC_TARGET", "localhost:50051")
SYNC_INITIAL_LOOKBACK_DAYS = int(os.environ.get("SYNC_INITIAL_LOOKBACK_DAYS", "7"))
SYNC_CURSOR_OVERLAP_SECONDS = int(os.environ.get("SYNC_CURSOR_OVERLAP_SECONDS", "300"))
ATS_HTTP_TIMEOUT_SECONDS = float(os.environ.get("ATS_HTTP_TIMEOUT_SECONDS", "10"))
