from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest
from pydantic import SecretStr

from novabridge_qa.config import Settings
from novabridge_qa.llm.anthropic_client import AnthropicClient
from novabridge_qa.llm.base import MAX_RETRIES, ChatMessage, LLMError
from novabridge_qa.llm.factory import build_llm
from novabridge_qa.llm.fake import FakeLLM
from novabridge_qa.llm.openai_compatible import OpenAICompatibleClient

SECRET = "sk-super-secret-value"
MESSAGES = [ChatMessage("user", "Hello"), ChatMessage("assistant", "Hi"), ChatMessage("user", "?")]


def make_openai() -> OpenAICompatibleClient:
    return OpenAICompatibleClient("http://llm.test/v1", SECRET, "m", temperature=0.1, timeout=5)


def make_anthropic() -> AnthropicClient:
    return AnthropicClient(SECRET, "m", timeout=5)


def fake_create(client: Any, result: Any) -> dict[str, Any]:
    """Replace the SDK call, returning what it was called with."""
    captured: dict[str, Any] = {}

    def create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    target = client._client
    if isinstance(client, AnthropicClient):
        target.messages.create = create
    else:
        target.chat.completions.create = create
    return captured


def openai_status_error(status: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "http://llm.test")
    response = httpx.Response(status, request=request)
    return openai.APIStatusError(f"Incorrect API key: {SECRET}", response=response, body=None)


def anthropic_status_error(status: int) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "http://llm.test")
    response = httpx2.Response(status, request=request)
    return anthropic.APIStatusError(f"Bad key: {SECRET}", response=response, body=None)


def openai_reply(content: str | None, finish_reason: str = "stop") -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


def anthropic_reply(*blocks: SimpleNamespace, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


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

    assert client.complete("be brief", MESSAGES, max_tokens=50) == "answer"

    assert captured["messages"][0] == {"role": "system", "content": "be brief"}
    assert [m["role"] for m in captured["messages"][1:]] == ["user", "assistant", "user"]
    assert captured["temperature"] == 0.1
    assert captured["max_tokens"] == 50
    assert captured["model"] == "m"


def test_anthropic_uses_the_system_parameter_and_sends_no_temperature() -> None:
    client = make_anthropic()
    captured = fake_create(client, anthropic_reply(text_block("answer")))

    assert client.complete("be brief", MESSAGES, max_tokens=50) == "answer"

    assert captured["system"] == "be brief"
    assert all(m["role"] != "system" for m in captured["messages"])
    assert "temperature" not in captured
    assert captured["max_tokens"] == 50


def test_retries_and_timeout_reach_the_sdk_clients() -> None:
    assert make_openai()._client.max_retries == MAX_RETRIES == 1
    assert make_anthropic()._client.max_retries == 1
    assert make_openai()._client.timeout == 5
    assert make_anthropic()._client.timeout == 5


def test_openai_client_starts_without_a_key_for_ollama() -> None:
    client = OpenAICompatibleClient("http://ollama:11434/v1", "", "m", temperature=0, timeout=5)

    assert client._client.api_key


# Responses that arrive as HTTP 200 but cannot be used


def test_anthropic_ignores_thinking_blocks() -> None:
    client = make_anthropic()
    thinking = SimpleNamespace(type="thinking", thinking="hmm")
    fake_create(client, anthropic_reply(thinking, text_block("part 1 "), text_block("part 2")))

    assert client.complete("s", MESSAGES, max_tokens=50) == "part 1 part 2"


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (anthropic_reply(text_block("partial"), stop_reason="max_tokens"), "LLM_MAX_TOKENS"),
        (anthropic_reply(stop_reason="refusal"), "declined"),
        (anthropic_reply(SimpleNamespace(type="thinking", thinking="hmm")), "empty"),
        (anthropic_reply(), "empty"),
    ],
)
def test_anthropic_unusable_responses(reply: SimpleNamespace, message: str) -> None:
    client = make_anthropic()
    fake_create(client, reply)

    with pytest.raises(LLMError, match=message):
        client.complete("s", MESSAGES, max_tokens=50)


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (openai_reply("partial", "length"), "LLM_MAX_TOKENS"),
        (openai_reply(None, "content_filter"), "declined"),
        (openai_reply(None), "empty"),
        (openai_reply(""), "empty"),
        (SimpleNamespace(choices=[]), "empty"),
    ],
)
def test_openai_unusable_responses(reply: SimpleNamespace, message: str) -> None:
    client = make_openai()
    fake_create(client, reply)

    with pytest.raises(LLMError, match=message):
        client.complete("s", MESSAGES, max_tokens=50)


# Error normalization


@pytest.mark.parametrize(("status", "message"), STATUS_MESSAGES)
def test_openai_status_errors_are_normalized(status: int, message: str) -> None:
    client = make_openai()
    fake_create(client, openai_status_error(status))

    with pytest.raises(LLMError, match=message) as caught:
        client.complete("s", MESSAGES, max_tokens=50)

    assert SECRET not in str(caught.value)
    assert isinstance(caught.value.__cause__, openai.APIStatusError)


@pytest.mark.parametrize(("status", "message"), STATUS_MESSAGES)
def test_anthropic_status_errors_are_normalized(status: int, message: str) -> None:
    client = make_anthropic()
    fake_create(client, anthropic_status_error(status))

    with pytest.raises(LLMError, match=message) as caught:
        client.complete("s", MESSAGES, max_tokens=50)

    assert SECRET not in str(caught.value)
    assert isinstance(caught.value.__cause__, anthropic.APIStatusError)


def test_timeouts_and_connection_errors_are_normalized() -> None:
    openai_request = httpx.Request("POST", "http://llm.test")
    anthropic_request = httpx2.Request("POST", "http://llm.test")
    cases: list[tuple[Any, Exception, str]] = [
        (make_openai(), openai.APITimeoutError(openai_request), "did not respond"),
        (make_openai(), openai.APIConnectionError(request=openai_request), "could not be reached"),
        (make_anthropic(), anthropic.APITimeoutError(anthropic_request), "did not respond"),
        (
            make_anthropic(),
            anthropic.APIConnectionError(request=anthropic_request),
            "could not be reached",
        ),
    ]
    for client, error, message in cases:
        fake_create(client, error)
        with pytest.raises(LLMError, match=message):
            client.complete("s", MESSAGES, max_tokens=50)


# Factory


def test_factory_builds_the_openai_compatible_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "some-model")

    assert isinstance(build_llm(Settings(_env_file=None)), OpenAICompatibleClient)


def test_factory_builds_the_anthropic_client() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="anthropic",
        anthropic_api_key=SecretStr("key"),
        anthropic_model="some-model",
    )

    assert isinstance(build_llm(settings), AnthropicClient)


def test_factory_requires_a_model_for_openai_compatible() -> None:
    with pytest.raises(ValueError, match="requires LLM_MODEL"):
        build_llm(Settings(_env_file=None))


def test_factory_requires_a_model_for_anthropic() -> None:
    settings = Settings(
        _env_file=None, llm_provider="anthropic", anthropic_api_key=SecretStr("key")
    )

    with pytest.raises(ValueError, match="requires ANTHROPIC_MODEL"):
        build_llm(settings)


# Fake


def test_fake_llm_replays_its_script_and_records_calls() -> None:
    llm = FakeLLM(["one", LLMError("boom")])

    assert llm.complete("s", MESSAGES, max_tokens=5) == "one"
    with pytest.raises(LLMError, match="boom"):
        llm.complete("s", MESSAGES, max_tokens=5)

    assert len(llm.calls) == 2
    assert llm.calls[0].system == "s"


def test_fake_llm_fails_when_called_too_often() -> None:
    with pytest.raises(AssertionError):
        FakeLLM([]).complete("s", MESSAGES, max_tokens=5)
