"""Send one tiny request to the configured LLM provider. This calls a real, possibly paid API.

Run from backend/: uv run python scripts/llm_smoke.py [--provider anthropic]
"""

import argparse
import sys
import time

from novabridge_qa.config import Settings
from novabridge_qa.llm.base import ChatMessage, LLMError
from novabridge_qa.llm.factory import build_llm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["openai_compatible", "anthropic"])
    args = parser.parse_args()

    overrides = {"llm_provider": args.provider} if args.provider else {}
    settings = Settings(**overrides)
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
    print(f"{settings.llm_provider}: {reply!r} in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
