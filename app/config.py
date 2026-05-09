from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./medical_chatbot.db"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    CORS_ORIGINS: str = "http://localhost:3000"
    APP_NAME: str = "Medical Chatbot CDSS"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    OPENAI_MAX_TOKENS: int = 1024
    OPENAI_TEMPERATURE: float = 0.3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()