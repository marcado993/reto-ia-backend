from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./medical_chatbot.db"

    # ── LLM (OpenRouter — API compatible con OpenAI) ───────────────
    # https://openrouter.ai/ — un solo key para muchos modelos.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    # Modelos actuales (revisa https://openrouter.ai/models): ej. google/gemini-2.5-pro,
    # openai/gpt-4o, anthropic/claude-sonnet-4, etc.
    OPENROUTER_MODEL: str = "openai/gpt-oss-20b:free"
    OPENROUTER_MAX_TOKENS: int = 2048
    OPENROUTER_TEMPERATURE: float = 0.3
    # Timeout por llamada (segundos). Críticamente importante con modelos free
    # que a veces tardan minutos o se cuelgan.
    OPENROUTER_TIMEOUT: float = 25.0
    # OpenRouter recomienda Referer público de tu app (opcional).
    OPENROUTER_HTTP_REFERER: str = "http://localhost:3000"

    # ── LLM legado (Google Gemini directo) — solo si NO hay OpenRouter
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
