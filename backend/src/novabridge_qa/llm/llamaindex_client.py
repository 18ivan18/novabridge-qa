"""A LlamaIndex `LLM` with the error handling the app relies on.

LlamaIndex makes the provider call. This wrapper keeps the behaviour the rest of the app relies on:
provider errors become `LLMError` messages that are safe to show, replies that arrive as HTTP 200
but cannot be used (cut off, refused, empty) raise instead of being returned, and token usage is
reported when the provider gives it.
"""

from collections.abc import Callable, Sequence
from typing import Any

import openai
from llama_index.core.base.llms.types import ChatMessage, ChatResponse, TextBlock
from llama_index.core.llms import LLM

from novabridge_qa.llm.base import (
    Completion,
    LLMError,
    connection_error,
    empty_error,
    status_error,
    timeout_error,
    truncated_error,
)

# Reads a reply into a Completion, or raises LLMError if it cannot be used. One per integration,
# because each keeps the provider's own response object in `ChatResponse.raw`.
ReplyReader = Callable[[ChatResponse, str], Completion]


def reply_text(reply: ChatResponse) -> str:
    """Join the text blocks with nothing between them, as the provider sent them.

    `ChatMessage.content` would join them with newlines.
    """
    return "".join(block.text for block in reply.message.blocks if isinstance(block, TextBlock))


def _token_count(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def read_openai_reply(reply: ChatResponse, provider: str) -> Completion:
    """`raw` is the SDK's ChatCompletion. LlamaIndex has already taken `choices[0]` from it."""
    finish_reason = reply.raw.choices[0].finish_reason if reply.raw is not None else None
    if finish_reason == "length":
        raise truncated_error(provider)
    if finish_reason == "content_filter":
        raise LLMError(f"{provider} declined to answer.")
    text = reply_text(reply)
    if not text:
        raise empty_error(provider)
    usage = getattr(reply.raw, "usage", None)
    return Completion(
        text,
        input_tokens=_token_count(getattr(usage, "prompt_tokens", None)),
        output_tokens=_token_count(getattr(usage, "completion_tokens", None)),
    )


class LlamaIndexClient:
    """The LLM is passed in, never read from LlamaIndex's global `Settings`, whose default is
    OpenAI."""

    def __init__(self, llm: LLM, *, provider: str, read_reply: ReplyReader) -> None:
        self.llm = llm
        self._provider = provider
        self._read_reply = read_reply

    def chat(self, messages: Sequence[ChatMessage], *, max_tokens: int) -> Completion:
        provider = self._provider
        # Both integrations let call kwargs override their defaults, so max_tokens is per call.
        # LlamaIndex re-raises the SDK's own exceptions, so they are mapped as before.
        try:
            reply = self.llm.chat(list(messages), max_tokens=max_tokens)
        except openai.APITimeoutError as error:
            raise timeout_error(provider) from error
        except openai.APIConnectionError as error:
            raise connection_error(provider) from error
        except openai.APIStatusError as error:
            raise status_error(provider, error.status_code) from error
        except openai.APIError as error:
            raise LLMError(f"{provider} returned an unexpected response.") from error
        except IndexError as error:
            # The OpenAI integration reads `choices[0]` without checking, and some
            # OpenAI-compatible servers answer with no choices at all.
            raise empty_error(provider) from error
        return self._read_reply(reply, provider)
