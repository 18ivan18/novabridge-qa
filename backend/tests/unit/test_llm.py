"""The LLM layer: LlamaIndex's OpenAILike behind our LlamaIndexClient.

The SDK call is replaced on the SDK client that LlamaIndex built, so each test runs the real
LlamaIndex code between our wrapper and the provider.
"""

from typing import Any

import httpx
import openai
import pytest
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage
from pydantic import SecretStr
from scripted_llm import FakeLLM

from novabridge_qa.config import Settings
from novabridge_qa.llm.base import MAX_RETRIES, Completion, LLMError, RateLimitError
from novabridge_qa.llm.factory import build_llm
from novabridge_qa.llm.llamaindex_client import LlamaIndexClient

SECRET = "sk-super-secret-value"
CONVERSATION = [
    ChatMessage(role=MessageRole.USER, content="Hello"),
    ChatMessage(role=MessageRole.ASSISTANT, content="Hi"),
    ChatMessage(role=MessageRole.USER, content="?"),
]
MESSAGES = [ChatMessage(role=MessageRole.SYSTEM, content="be brief"), *CONVERSATION]


def openai_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "llm_base_url": "http://llm.test/v1",
        "llm_api_key": SecretStr(SECRET),
        "llm_model": "m",
        "llm_temperature": 0.1,
        "llm_timeout_seconds": 5,
    }
    return Settings(_env_file=None, **{**values, **overrides})


def make_openai(**overrides: Any) -> LlamaIndexClient:
    client = build_llm(openai_settings(**overrides))
    assert isinstance(client, LlamaIndexClient)
    return client


def sdk_client(client: LlamaIndexClient) -> Any:
    """The SDK client LlamaIndex will call."""
    llm: Any = client.llm
    return llm._get_client()


def fake_create(client: LlamaIndexClient, result: Any) -> dict[str, Any]:
    """Replace the SDK call, returning what it was last called with and how often."""
    captured: dict[str, Any] = {"count": 0}

    def create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        captured["count"] += 1
        if isinstance(result, Exception):
            raise result
        return result

    sdk_client(client).chat.completions.create = create
    return captured


def openai_status_error(status: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "http://llm.test")
    response = httpx.Response(status, request=request)
    return openai.APIStatusError(f"Incorrect API key: {SECRET}", response=response, body=None)


def openai_reply(
    content: str | None,
    finish_reason: Any = "stop",
    usage: CompletionUsage | None = None,
) -> ChatCompletion:
    message = ChatCompletionMessage(role="assistant", content=content)
    choice = Choice(index=0, finish_reason=finish_reason, message=message)
    return ChatCompletion(
        id="c", created=0, model="m", object="chat.completion", choices=[choice], usage=usage
    )


STATUS_MESSAGES = [
    (401, "rejected the API key"),
    (403, "rejected the API key"),
    (404, "does not recognize the configured model"),
    (429, "rate limit"),
    (500, "having problems"),
    (503, "having problems"),
    (400, "rejected the request"),
]


# Requests


def test_openai_puts_system_first_and_sends_temperature() -> None:
    client = make_openai()
    captured = fake_create(client, openai_reply("answer"))

    assert client.chat(MESSAGES, max_tokens=50).text == "answer"

    assert captured["messages"][0] == {"role": "system", "content": "be brief"}
    assert [m["role"] for m in captured["messages"][1:]] == ["user", "assistant", "user"]
    assert captured["temperature"] == 0.1
    assert captured["max_tokens"] == 50
    assert captured["model"] == "m"


def test_max_tokens_is_set_per_call() -> None:
    client = make_openai()
    captured = fake_create(client, openai_reply("answer"))

    client.chat(MESSAGES, max_tokens=50)
    client.chat(MESSAGES, max_tokens=7)

    assert captured["max_tokens"] == 7


def test_retries_and_timeout_reach_the_sdk_clients() -> None:
    assert sdk_client(make_openai()).max_retries == MAX_RETRIES == 1
    assert sdk_client(make_openai()).timeout == 5


def test_llamaindex_adds_no_retries_on_top_of_the_sdk() -> None:
    # LlamaIndex wraps OpenAI calls in its own tenacity retry; with max_retries=1 it must make
    # exactly one SDK call (the SDK's own single retry happens inside that call).
    client = make_openai()
    captured = fake_create(client, openai_status_error(503))

    with pytest.raises(LLMError):
        client.chat(MESSAGES, max_tokens=50)

    assert captured["count"] == 1


def test_openai_client_starts_without_a_key_for_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty key would make LlamaIndex fall back to OPENAI_API_KEY.
    monkeypatch.setenv("OPENAI_API_KEY", "a-key-for-something-else")

    client = make_openai(llm_base_url="http://ollama:11434/v1", llm_api_key=SecretStr(""))

    assert sdk_client(client).api_key == "not-needed"


# Responses that arrive as HTTP 200, and token usage


def test_openai_reports_token_usage() -> None:
    client = make_openai()
    usage = CompletionUsage(prompt_tokens=120, completion_tokens=8, total_tokens=128)
    fake_create(client, openai_reply("answer", usage=usage))

    assert client.chat(MESSAGES, max_tokens=50) == Completion("answer", 120, 8)


def test_openai_usage_is_none_when_the_provider_omits_it() -> None:
    client = make_openai()
    fake_create(client, openai_reply("answer"))

    assert client.chat(MESSAGES, max_tokens=50) == Completion("answer", None, None)


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (openai_reply("partial", "length"), "LLM_MAX_TOKENS"),
        (openai_reply(None, "content_filter"), "declined"),
        (openai_reply(None), "empty"),
        (openai_reply(""), "empty"),
        (
            ChatCompletion(id="c", created=0, model="m", object="chat.completion", choices=[]),
            "empty",
        ),
    ],
)
def test_openai_unusable_responses(reply: ChatCompletion, message: str) -> None:
    client = make_openai()
    fake_create(client, reply)

    with pytest.raises(LLMError, match=message):
        client.chat(MESSAGES, max_tokens=50)


# Error normalization


@pytest.mark.parametrize(("status", "message"), STATUS_MESSAGES)
def test_openai_status_errors_are_normalized(status: int, message: str) -> None:
    client = make_openai()
    fake_create(client, openai_status_error(status))

    with pytest.raises(LLMError, match=message) as caught:
        client.chat(MESSAGES, max_tokens=50)

    assert SECRET not in str(caught.value)
    assert isinstance(caught.value.__cause__, openai.APIStatusError)


def test_rate_limits_raise_a_distinct_error() -> None:
    client = make_openai()
    fake_create(client, openai_status_error(429))

    with pytest.raises(RateLimitError):
        client.chat(MESSAGES, max_tokens=50)


def test_timeouts_and_connection_errors_are_normalized() -> None:
    request = httpx.Request("POST", "http://llm.test")
    cases: list[tuple[LlamaIndexClient, Exception, str]] = [
        (make_openai(), openai.APITimeoutError(request), "did not respond"),
        (make_openai(), openai.APIConnectionError(request=request), "could not be reached"),
    ]
    for client, error, message in cases:
        fake_create(client, error)
        with pytest.raises(LLMError, match=message):
            client.chat(MESSAGES, max_tokens=50)


# Factory


def test_factory_builds_openai_like(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "some-model")

    client = build_llm(Settings(_env_file=None))

    assert isinstance(client, LlamaIndexClient)
    assert type(client.llm).__name__ == "OpenAILike"
    assert client.llm.metadata.is_chat_model


def test_factory_requires_a_model_for_openai_compatible() -> None:
    with pytest.raises(ValueError, match="requires LLM_MODEL"):
        build_llm(Settings(_env_file=None))


# Fake


def test_fake_llm_replays_its_script_and_records_calls() -> None:
    llm = FakeLLM(["one", Completion("two", 10, 2), LLMError("boom")])

    assert llm.chat(MESSAGES, max_tokens=5) == Completion("one")
    assert llm.chat(MESSAGES, max_tokens=5) == Completion("two", 10, 2)
    with pytest.raises(LLMError, match="boom"):
        llm.chat(MESSAGES, max_tokens=5)

    assert len(llm.calls) == 3
    assert llm.calls[0].system == "be brief"
    assert llm.calls[0].messages == tuple(CONVERSATION)
    assert llm.calls[0].max_tokens == 5


def test_fake_llm_fails_when_called_too_often() -> None:
    with pytest.raises(AssertionError):
        FakeLLM([]).chat(MESSAGES, max_tokens=5)
