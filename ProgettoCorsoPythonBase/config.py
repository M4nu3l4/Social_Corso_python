# config.py
from pathlib import Path
import os

# Cartelle base
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

STATIC_DIR = BASE_DIR / "app" / "static"
UPLOAD_FOLDER = STATIC_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


class Config:
    # --- Sicurezza / App ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{INSTANCE_DIR / 'social.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Static / Upload ---
    STATIC_DIR = STATIC_DIR  # Path object (usato nell’app)
    UPLOAD_FOLDER = UPLOAD_FOLDER  # Path object (usato nell’app)
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB (anche video)

    # --- Estensioni file ammesse ---
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "avi", "mkv"}
    ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS


# --- Moderazione (soglie regolabili) ---
# score < PENDING => approve ; PENDING <= score < REJECT => pending ; score >= REJECT => reject
TOXICITY_PENDING_THRESHOLD = 0.60
TOXICITY_REJECT_THRESHOLD = 0.80
# --- Moderazione: amministratori (email che possono usare la dashboard admin) ---
# Popola con le email reali, es: ["prof@example.com", "tutor@example.com"]
ADMIN_EMAILS = [
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
]

# --- Rate limiting (se usi Flask-Limiter) ---
# Storage in memoria per dev; in produzione usa Redis: "redis://localhost:6379/0"
RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
# Limite di fallback per endpoint non decorati (opzionale)
RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "100 per 5 minutes")
