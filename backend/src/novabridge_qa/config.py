"""Application settings, loaded from the environment and `.env`."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Every value here has a matching entry in `.env.example`; a test keeps the two in sync."""

    # `.env` lives at the repo root because docker compose reads it from there too. Paths are
    # relative to the working directory, so list both places a developer runs commands from.
    # hide_input_in_errors: a validation error would otherwise echo raw values, keys included.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), extra="ignore", hide_input_in_errors=True
    )

    llm_provider: Literal["openai_compatible", "anthropic"] = "openai_compatible"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    # SecretStr keeps keys out of logs and tracebacks: repr() prints asterisks.
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = ""
    llm_temperature: float = 0.1
    llm_max_tokens: int = 700

    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_device: str = "cpu"

    data_dir: Path = Path("./data")
    chunk_tokens: int = 400
    chunk_overlap: int = 60
    retrieval_candidates: int = 20
    top_k: int = 6
    rrf_k: int = 60
    min_relevance: float = 0.35
    max_upload_mb: int = 20
    # NoDecode: pydantic-settings would otherwise parse list fields as JSON and reject a plain URL.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    sec_user_agent: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        """Fail at startup with a clear message, not on an analyst's first question."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key.get_secret_value():
            raise ValueError("LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY to be set")
        if self.chunk_overlap >= self.chunk_tokens:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_TOKENS")
        return self
