"""Ask a question end to end. This calls the configured LLM provider, which may be paid.

Run from backend/: uv run python scripts/ask.py "your question"
"""

import argparse
import sys

from novabridge_qa.config import Settings
from novabridge_qa.container import build_dense_index, build_qa_service
from novabridge_qa.llm.base import LLMError
from novabridge_qa.qa.prompt import passage_source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    args = parser.parse_args()

    settings = Settings()
    service = build_qa_service(settings, build_dense_index(settings))
    try:
        answer = service.ask(args.question)
    except LLMError as error:
        sys.exit(f"FAILED: {error}")

    print(answer.text if not answer.insufficient_evidence else "[not enough evidence]")
    for source in answer.sources:
        print(f"  [{source.id}] {passage_source(source.passage)}")
    print(
        f"  ({len(answer.sources)} cited of {len(answer.retrieved)} retrieved, "
        f"retrieval {answer.retrieval_ms} ms, generation {answer.generation_ms} ms)"
    )


if __name__ == "__main__":
    main()
