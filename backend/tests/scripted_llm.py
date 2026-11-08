"""A scripted LLM for tests: a LlamaIndex `CustomLLM` behind the same wrapper as the real ones."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from llama_index.core.base.llms.types import ChatMessage as LIChatMessage
from llama_index.core.base.llms.types import (
    ChatResponse,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
    MessageRole,
)
from llama_index.core.llms import CustomLLM
from pydantic import Field

from novabridge_qa.llm.base import ChatMessage, Completion
from novabridge_qa.llm.llamaindex_client import LlamaIndexClient, reply_text

Reply = str | Completion | Exception


@dataclass(frozen=True)
class RecordedCall:
    system: str
    messages: tuple[ChatMessage, ...]
    max_tokens: int


class ScriptedLLM(CustomLLM):
    """Returns each scripted reply in turn. An exception in the script is raised instead.

    `chat` is overridden so the system prompt and messages are recorded as sent, rather than
    flattened into one prompt string the way `CustomLLM.chat` does.
    """

    replies: list[Reply] = Field(default_factory=list)
    calls: list[RecordedCall] = Field(default_factory=list)

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(is_chat_model=True, model_name="scripted")

    def chat(self, messages: Sequence[LIChatMessage], **kwargs: Any) -> ChatResponse:
        system = "".join(m.content or "" for m in messages if m.role == MessageRole.SYSTEM)
        conversation = tuple(
            ChatMessage("user" if m.role == MessageRole.USER else "assistant", m.content or "")
            for m in messages
            if m.role != MessageRole.SYSTEM
        )
        self.calls.append(RecordedCall(system, conversation, kwargs["max_tokens"]))
        reply = self._next()
        # The same keys LlamaIndex's OpenAI integration uses for token counts.
        usage = {"prompt_tokens": reply.input_tokens, "completion_tokens": reply.output_tokens}
        return ChatResponse(
            message=LIChatMessage(role=MessageRole.ASSISTANT, content=reply.text),
            additional_kwargs=usage,
        )

    def complete(self, prompt: str, formatted: bool = False, **kwargs: Any) -> CompletionResponse:
        return CompletionResponse(text=self._next().text)

    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        raise NotImplementedError("The app does not stream.")

    def _next(self) -> Completion:
        if not self.replies:
            raise AssertionError("FakeLLM was called more often than scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return Completion(reply) if isinstance(reply, str) else reply


def read_scripted_reply(reply: ChatResponse, provider: str) -> Completion:
    usage = reply.additional_kwargs
    return Completion(
        reply_text(reply),
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )


class FakeLLM(LlamaIndexClient):
    """`LLMClient` over a `ScriptedLLM`. A plain string becomes a Completion with no token
    counts."""

    def __init__(self, replies: list[Reply]) -> None:
        self.script = ScriptedLLM(replies=replies)
        super().__init__(self.script, provider="The fake LLM", read_reply=read_scripted_reply)

    @property
    def calls(self) -> list[RecordedCall]:
        return self.script.calls
