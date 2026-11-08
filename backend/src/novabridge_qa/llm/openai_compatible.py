"""Any provider speaking the OpenAI chat API: Groq, Ollama or OpenAI, chosen by `base_url`."""

from collections.abc import Sequence

import openai
from openai.types.chat import ChatCompletionMessageParam

from novabridge_qa.llm.base import (
    MAX_RETRIES,
    ChatMessage,
    Completion,
    LLMError,
    connection_error,
    empty_error,
    status_error,
    timeout_error,
    truncated_error,
)

PROVIDER = "The LLM provider"


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        temperature: float,
        timeout: float,
    ) -> None:
        self._client = openai.OpenAI(
            base_url=base_url,
            # Ollama needs no key, but the SDK refuses to start without one.
            api_key=api_key or "not-needed",
            timeout=timeout,
            max_retries=MAX_RETRIES,
        )
        self._model = model
        self._temperature = temperature

    def complete(
        self, system: str, messages: Sequence[ChatMessage], *, max_tokens: int
    ) -> Completion:
        chat: list[ChatCompletionMessageParam] = [{"role": "system", "content": system}]
        for message in messages:
            if message.role == "user":
                chat.append({"role": "user", "content": message.content})
            else:
                chat.append({"role": "assistant", "content": message.content})

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=chat,
                max_tokens=max_tokens,
                temperature=self._temperature,
            )
        except openai.APITimeoutError as error:
            raise timeout_error(PROVIDER) from error
        except openai.APIConnectionError as error:
            raise connection_error(PROVIDER) from error
        except openai.APIStatusError as error:
            raise status_error(PROVIDER, error.status_code) from error
        except openai.APIError as error:
            raise LLMError(f"{PROVIDER} returned an unexpected response.") from error

        if not response.choices:
            raise empty_error(PROVIDER)
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise truncated_error(PROVIDER)
        if choice.finish_reason == "content_filter":
            raise LLMError(f"{PROVIDER} declined to answer.")
        if not choice.message.content:
            raise empty_error(PROVIDER)
        usage = response.usage
        return Completion(
            choice.message.content,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )
