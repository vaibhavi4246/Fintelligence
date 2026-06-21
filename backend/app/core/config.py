"""Application settings, loaded from environment / .env.

Centralizes provider configuration so the LLM (Groq -> Ollama fallback) and
embedding (bge -> OpenAI fallback) layers read from one place.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql://findocint:findocint@localhost:5432/findocint"

    # LLM provider (claim extraction). Groq primary, Ollama fallback.
    llm_provider: str = "groq"  # "groq" | "ollama"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:14b-instruct"

    # Embedding provider. bge (local, 768-dim) primary, OpenAI fallback.
    embedding_provider: str = "bge"  # "bge" | "openai"
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768
    openai_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
