"""Anthropic's Messages API."""

from collections.abc import Sequence

import anthropic
from anthropic.types import MessageParam

from novabridge_qa.llm.base import (
    MAX_RETRIES,
    ChatMessage,
    LLMError,
    connection_error,
    empty_error,
    status_error,
    timeout_error,
    truncated_error,
)

PROVIDER = "Anthropic"


class AnthropicClient:
    """Sends no `temperature`: API version 2026-10-21 rejects it with a 400 on every model."""

    def __init__(self, api_key: str, model: str, *, timeout: float) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=MAX_RETRIES
        )
        self._model = model

    def complete(self, system: str, messages: Sequence[ChatMessage], *, max_tokens: int) -> str:
        chat: list[MessageParam] = []
        for message in messages:
            if message.role == "user":
                chat.append({"role": "user", "content": message.content})
            else:
                chat.append({"role": "assistant", "content": message.content})

        try:
            response = self._client.messages.create(
                model=self._model,
                system=system,
                messages=chat,
                max_tokens=max_tokens,
            )
        except anthropic.APITimeoutError as error:
            raise timeout_error(PROVIDER) from error
        except anthropic.APIConnectionError as error:
            raise connection_error(PROVIDER) from error
        except anthropic.APIStatusError as error:
            raise status_error(PROVIDER, error.status_code) from error
        except anthropic.APIError as error:
            raise LLMError(f"{PROVIDER} returned an unexpected response.") from error

        # These arrive as HTTP 200, so no exception signals them.
        if response.stop_reason == "refusal":
            raise LLMError(f"{PROVIDER} declined to answer.")
        if response.stop_reason == "max_tokens":
            raise truncated_error(PROVIDER)

        # Responses can also hold thinking blocks, which are not part of the answer.
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text:
            raise empty_error(PROVIDER)
        return text
