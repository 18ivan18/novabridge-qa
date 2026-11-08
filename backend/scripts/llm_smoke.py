"""Send one tiny request to the configured LLM provider. This calls a real, possibly paid API.

Run from backend/: uv run python scripts/llm_smoke.py
"""

import argparse
import sys
import time

from novabridge_qa.config import Settings
from novabridge_qa.llm.base import ChatMessage, LLMError
from novabridge_qa.llm.factory import build_llm


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()

    settings = Settings()
    llm = build_llm(settings)

    started = time.perf_counter()
    try:
        reply = llm.complete(
            "Reply with exactly one word.",
            [ChatMessage("user", "What is the opposite of 'up'?")],
            max_tokens=settings.llm_max_tokens,
        )
    except LLMError as error:
        sys.exit(f"{settings.llm_provider}: FAILED: {error}")
    elapsed = time.perf_counter() - started
    tokens = f"{reply.input_tokens} in, {reply.output_tokens} out"
    print(f"{settings.llm_provider}: {reply.text!r} in {elapsed:.1f}s ({tokens} tokens)")


if __name__ == "__main__":
    main()
