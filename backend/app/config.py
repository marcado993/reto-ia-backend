from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./medical_chatbot.db"

    # ── LLM (Google Gemini / AI Studio) ─────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_TOKENS: int = 1024
    GEMINI_TEMPERATURE: float = 0.3

    # ── EndlessMedical (detección de enfermedad, API pública) ──────
    # No requiere API key. Es session-based.
    ENDLESS_MEDICAL_BASE: str = "https://api.endlessmedical.com/v1/dx"
    ENDLESS_MEDICAL_TIMEOUT: float = 15.0

    # ── App ─────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"
    APP_NAME: str = "Medical Chatbot CDSS"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
