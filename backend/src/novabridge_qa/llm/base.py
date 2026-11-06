"""The interface every LLM provider implements."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

# The SDKs retry timeouts, connection errors, 429s and 5xx themselves, with backoff.
MAX_RETRIES = 1


class LLMError(Exception):
    """A provider failure.

    The message is written here and is safe to show to users. It never repeats the provider's
    own text, because a 401 body can quote part of the API key. The SDK error stays available as
    `__cause__` for logs.
    """


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


class LLMClient(Protocol):
    def complete(self, system: str, messages: Sequence[ChatMessage], *, max_tokens: int) -> str: ...


def status_error(provider: str, status: int) -> LLMError:
    if status in (401, 403):
        return LLMError(f"{provider} rejected the API key.")
    if status == 404:
        return LLMError(f"{provider} does not recognize the configured model.")
    if status == 429:
        return LLMError(f"{provider} rate limit reached. Try again shortly.")
    if status >= 500:
        return LLMError(f"{provider} is having problems. Try again shortly.")
    return LLMError(f"{provider} rejected the request (status {status}).")


def timeout_error(provider: str) -> LLMError:
    return LLMError(f"{provider} did not respond in time.")


def connection_error(provider: str) -> LLMError:
    return LLMError(f"{provider} could not be reached.")


def truncated_error(provider: str) -> LLMError:
    # A cut-off answer can lose a citation or a qualifier, so it is not returned as an answer.
    return LLMError(f"{provider} ran out of output tokens. Raise LLM_MAX_TOKENS.")


def empty_error(provider: str) -> LLMError:
    return LLMError(f"{provider} returned an empty response.")
