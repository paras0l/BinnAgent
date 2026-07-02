from pydantic import AliasChoices, Field
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
    knowledge_upload_dir: str = "var/knowledge/uploads"
    knowledge_max_upload_bytes: int = 52_428_800
    knowledge_chunk_size: int = 900
    knowledge_chunk_overlap: int = 150
    knowledge_embedding_dimensions: int = 768
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str = "http://localhost:3100"
    langfuse_environment: str = "development"
    debug: bool = False
    debug_console_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("BINN_DEBUG_CONSOLE_ENABLED", "DEBUG_CONSOLE_ENABLED"),
    )
    debug_console_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("BINN_DEBUG_CONSOLE_TOKEN", "DEBUG_CONSOLE_TOKEN"),
    )
    debug_console_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5174"],
        validation_alias=AliasChoices(
            "BINN_DEBUG_CONSOLE_ALLOWED_ORIGINS",
            "DEBUG_CONSOLE_ALLOWED_ORIGINS",
        ),
    )


settings = Settings()
