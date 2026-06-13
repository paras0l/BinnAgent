from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BINN_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://binn:binn@localhost:5432/binn_agent"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "gemma4:e2b"
    ollama_utility_model: str = "gemma4:e2b"
    ollama_embedding_model: str = "nomic-embed-text:latest"
    chat_max_tokens: int = 2048
    chat_history_limit: int = 12
    chat_auto_continue_limit: int = 2
    fallback_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    debug: bool = False


settings = Settings()
