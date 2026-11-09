# NovaBridge Q&A

Read `docs/HANDOFF.md` fully before writing code. It holds the decisions, milestones and rules.

## Commands

Backend (from `backend/`):

    uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
    uv run uvicorn novabridge_qa.main:create_app --factory

Frontend (from `frontend/`, once it exists):

    npm run lint && npm run typecheck && npm test

## Rules

- One milestone at a time; run the checks and wait for Ivan's approval before starting the next.
- On this branch (`spike/llamaindex`) LlamaIndex does the plumbing: Chroma, BM25, RRF, chunk
  packing, ingestion and the LLM call. Do not replace it with hand-written code. Section detection,
  the relevance gate, the refusal marker, the prompt and the citation check stay ours, as
  LlamaIndex components. Read `docs/LLAMAINDEX_SPIKE.md` (its corrections list the traps) before
  changing retrieval or ingestion. No LangChain.
- Ask before adding a dependency not listed in section 4 of the handoff.
- No secrets in the repo. No invented facts in fixtures or the README.
- If the handoff is wrong or blocks you, stop and say so.
