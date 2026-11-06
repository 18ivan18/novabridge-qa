"""A scripted LLM for tests."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from novabridge_qa.llm.base import ChatMessage


@dataclass(frozen=True)
class RecordedCall:
    system: str
    messages: tuple[ChatMessage, ...]
    max_tokens: int


@dataclass
class FakeLLM:
    """Returns each scripted reply in turn. An exception in the script is raised instead."""

    replies: list[str | Exception]
    calls: list[RecordedCall] = field(default_factory=list)

    def complete(self, system: str, messages: Sequence[ChatMessage], *, max_tokens: int) -> str:
        self.calls.append(RecordedCall(system, tuple(messages), max_tokens))
        if not self.replies:
            raise AssertionError("FakeLLM was called more often than scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
