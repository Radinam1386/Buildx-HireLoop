import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT.parent / ".env")  # .env در ریشهٔ پروژه
load_dotenv(ROOT / ".env")


def _b(v: str, default: bool) -> bool:
    return default if v == "" else v.strip().lower() in ("1", "true", "yes")


class Settings:
    base_url = os.getenv("LLM_BASE_URL", "")
    api_key = os.getenv("LLM_API_KEY", "")
    model_interviewer = os.getenv("MODEL_INTERVIEWER", "")
    model_matcher = os.getenv("MODEL_MATCHER", "")
    model_writer = os.getenv("MODEL_WRITER", "")
    model_refiner = os.getenv("MODEL_REFINER", "")
    model_utility = os.getenv("MODEL_UTILITY", "") or os.getenv("MODEL_INTERVIEWER", "")
    embedding_model = os.getenv("EMBEDDING_MODEL", "")
    reasoning_effort = os.getenv("REASONING_EFFORT", "").strip()
    json_mode = _b(os.getenv("JSON_MODE", ""), True)
    match_top_k = int(os.getenv("MATCH_TOP_K", "8") or 8)
    jwt_secret = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_hours = int(os.getenv("JWT_EXPIRE_HOURS", "72") or 72)
    database_url = os.getenv("DATABASE_URL", "sqlite:///./hireloop.db")
    cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]


S = Settings()
