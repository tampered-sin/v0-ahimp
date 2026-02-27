"""
Application configuration – reads from environment variables or .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
PKL_DIR  = BASE_DIR / "models" / "pkl"
DATA_DIR = BASE_DIR / "data"
PKL_DIR.mkdir(parents=True, exist_ok=True)

# ── Database ──────────────────────────────────────────────────────────────────
# Default: SQLite (zero-setup for dev).  Set DATABASE_URL env var for Postgres.
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'ahimp.db'}"
)

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# ── ML Hyper-params ───────────────────────────────────────────────────────────
RANDOM_SEED = 42
FORECAST_HORIZON = 14        # days to forecast
STOCKOUT_HORIZON = 7         # look-ahead window for stockout label
EXPIRY_RISK_THRESHOLD = 0.5  # logistic regression threshold
