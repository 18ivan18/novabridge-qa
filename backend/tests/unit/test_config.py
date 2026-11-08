from pathlib import Path

import pytest
from pydantic import ValidationError

from novabridge_qa.config import Settings

ENV_EXAMPLE = Path(__file__).parents[3] / ".env.example"


def test_defaults_need_no_env_file() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "openai_compatible"
    assert settings.rrf_k == 60


def test_anthropic_provider_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    # Not available on the LlamaIndex branch: see docs/LLAMAINDEX_SPIKE.md, "Corrections".
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")

    with pytest.raises(ValidationError, match="openai_compatible"):
        Settings(_env_file=None)


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "acme")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_overlap_must_be_smaller_than_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUNK_TOKENS", "100")
    monkeypatch.setenv("CHUNK_OVERLAP", "100")

    with pytest.raises(ValidationError, match="CHUNK_OVERLAP"):
        Settings(_env_file=None)


def test_cors_origins_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")

    assert Settings(_env_file=None).cors_origins == ["http://a.test", "http://b.test"]


def test_api_keys_do_not_appear_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "super-secret-value")

    assert "super-secret-value" not in repr(Settings(_env_file=None))


def test_api_keys_do_not_appear_in_validation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_API_KEY", "super-secret-value")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert "super-secret-value" not in str(error.value)


def test_env_example_mirrors_settings() -> None:
    lines = ENV_EXAMPLE.read_text().splitlines()
    example_keys = {
        line.split("=", 1)[0] for line in lines if line.strip() and not line.startswith("#")
    }

    assert example_keys == {name.upper() for name in Settings.model_fields}


def test_env_example_loads_and_matches_defaults() -> None:
    assert Settings(_env_file=ENV_EXAMPLE) == Settings(_env_file=None)
