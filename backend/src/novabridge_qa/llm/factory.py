"""Build the LLM client that the settings ask for."""

from llama_index.llms.openai_like import OpenAILike

from novabridge_qa.config import Settings
from novabridge_qa.llm.base import MAX_RETRIES, LLMClient
from novabridge_qa.llm.llamaindex_client import LlamaIndexClient, read_openai_reply


def build_llm(settings: Settings) -> LLMClient:
    """Groq, Ollama or OpenAI through LlamaIndex's OpenAILike, chosen by LLM_BASE_URL."""
    if not settings.llm_model:
        raise ValueError("LLM_PROVIDER=openai_compatible requires LLM_MODEL to be set")
    openai_like = OpenAILike(
        model=settings.llm_model,
        api_base=settings.llm_base_url,
        # Ollama needs no key, but the SDK refuses to start without one. An empty key would also
        # make LlamaIndex fall back to the OPENAI_API_KEY variable.
        api_key=settings.llm_api_key.get_secret_value() or "not-needed",
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        # The SDK retries once. LlamaIndex wraps the call in its own retry, which runs
        # stop_after_attempt(max_retries), so 1 adds no second layer on top.
        max_retries=MAX_RETRIES,
        # The chat completions endpoint; the default (False) uses the legacy completions one.
        is_chat_model=True,
    )
    return LlamaIndexClient(openai_like, provider="The LLM provider", read_reply=read_openai_reply)
