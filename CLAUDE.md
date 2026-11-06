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
- No LangChain or LlamaIndex.
- Ask before adding a dependency not listed in section 4 of the handoff.
- No secrets in the repo. No invented facts in fixtures or the README.
- If the handoff is wrong or blocks you, stop and say so.
