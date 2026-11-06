# HANDOFF — NovaBridge Financial Analyst Q&A Assistant

> For the Claude Code agent working in this repo. Read this file fully before writing code.
> The owner is **Ivan**, a backend engineer (TypeScript/Node, Kafka, AWS) for whom Python is the weaker
> production language. This repo is a **take-home task for an interview at EPAM (AI-Python role)**.
> Ivan must be able to explain and defend **every line** in a follow-up technical interview.

---

## 1. What we are building

An internal prototype for a (fictional) boutique advisory firm, NovaBridge Finance. Analysts ask questions
about financial documents and get a **short, synthesized answer backed by verifiable, numbered citations**
to the passages the answer came from.

Required deliverables (from the brief, in `docs/BRIEF.md`):

1. A **Python backend** exposing an API that answers questions from ingested financial documents.
2. A **web frontend** (we use **Vite + React + TypeScript**) to ask a question and see the answer with sources.
3. A **README.md** explaining design choices, trade-offs, setup and how to run.
4. **Full, unedited logs of every AI-assistant conversation** used (committed under `ai-logs/`).

The brief explicitly says: *"This task tests your judgment and ability to verify AI-generated code"* and
*"We value good design, clear reasoning, and a functional end-to-end system over complex, half-finished features."*

### What the reviewers will look for

- RAG done properly: loading, chunking, indexing, hybrid retrieval, grounded generation, **citations that are
  checked server-side**.
- **Honesty:** when the documents don't contain the answer, say so (no answer is written).
- A system that runs end to end with one command (`docker compose up`) and has tests.
- Clean, idiomatic, typed Python with a clear package layout.
- A chat log showing the human reviewing, testing and pushing back, not just accepting generated code.

---

## 2. Rules for the agent

1. **One milestone at a time** (section 9). Finish it, run the checks, show Ivan the result, and wait for
   approval before starting the next one. Make one commit per milestone (or smaller), using clear conventional
   commit messages.
2. **Before every commit:** `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`
   in `backend/`, and `npm run lint && npm run typecheck && npm test` in `frontend/` once it exists.
3. **No LangChain, no LlamaIndex.** The core is plain Python behind small interfaces (decision D1). Don't
   add a framework to "save time".
4. **Ask before adding any dependency** not listed in section 4. Give a one-line reason.
5. **Prefer clarity over cleverness.** Small functions, explicit types, no metaprogramming, no global
   mutable state except the app container built in `main.py`.
6. **Explain non-obvious choices** in a short comment or docstring that says *why*, not *what*.
7. **Never invent facts in fixtures or the README.** Test fixtures use obviously synthetic text
   ("ACME Corp…"). Financial content only comes from the real filings in `backend/data/raw/`.
8. **No secrets in the repo.** All keys come from `.env` (gitignored). Keep `.env.example` up to date.
9. **Don't hard-code LLM model IDs as facts.** Put them in `.env.example` with a comment saying to check
   the provider's current model list.
10. If something in this handoff is wrong or blocks you, **stop and say so** instead of working around it.

---

## 3. Decisions already made (with the reasoning Ivan will defend)

| # | Decision | Why |
|---|---|---|
| D1 | Plain Python core, **no LlamaIndex/LangChain** | Every step (chunking, fusion, prompt, citation check) is visible, testable and explainable. LlamaIndex would duplicate our own LLM adapter layer and hide the citation logic in its templates. Trade-off: more code; the brief only *suggests* frameworks. |
| D2 | **LLM behind an adapter interface**, provider chosen by env var | `LLM_PROVIDER=openai_compatible` (Groq, Ollama, OpenAI by changing `base_url`) or `anthropic`. Shows clean ports-and-adapters design, keeps the system runnable for free (Groq/Ollama), and lets tests use a `FakeLLM`. |
| D3 | **Embedder is a separate interface** from the LLM | Anthropic has no embeddings API, so the embedding provider can't follow the LLM provider. |
| D4 | Embeddings: **Qwen3-Embedding-0.6B** (Apache 2.0) via `sentence-transformers`, CPU | One of the strongest small open models (Oct 2026 MTEB); runs locally, free, offline. Alternative to compare in the evaluation: `microsoft/harrier-oss-v1-0.6b` (MIT). Final choice decided by **our own recall@k**, not the leaderboard. Trade-off: PyTorch makes the Docker image big; use CPU-only torch wheels. |
| D5 | **Hybrid retrieval**: BM25 (`bm25s`) + dense (Chroma), merged with **Reciprocal Rank Fusion** written by hand | Financial text is full of exact terms (tickers, "Item 1A", product names, numbers) where BM25 wins, and paraphrased questions where dense wins. RRF needs no score calibration. `score(d) = Σ 1/(k + rank_i(d))`, k = 60 (Cormack et al., 2009). About 15 lines; unit-tested. |
| D6 | **Vector store: ChromaDB** (persistent, embedded) | Zero ops, stores text + metadata, good enough for thousands of chunks. Chroma is the **single source of truth** for chunks; the BM25 index is derived from it and can be rebuilt. |
| D7 | **Citations checked on the server** | Passages are numbered `[1]..[k]` in the prompt; the model must cite `[n]`. The server parses citations, drops numbers that don't exist, renumbers the rest in order of first appearance, and returns only cited passages as `sources`. Zero valid citations → treated as insufficient evidence. |
| D8 | **"Not enough evidence" path** has two layers | (a) Retrieval gate: if the best dense cosine similarity < `MIN_RELEVANCE` (tuned on the eval set), the LLM is not called. (b) The model is told to reply exactly `INSUFFICIENT_EVIDENCE` if the passages don't answer the question. Either case returns `insufficient_evidence: true`. |
| D9 | **Corpus: SEC EDGAR 10-K filings** for Apple, Microsoft and NVIDIA (latest annual report each) | Real, relevant, and US government filings are public domain, so they can be committed. EDGAR requires a descriptive `User-Agent` with contact info: read it from `SEC_USER_AGENT` in `.env`, never hard-code it. |
| D10 | **Document upload** from the UI | `POST /api/documents` (multipart). Indexing runs as a background job; the UI polls job status. Formats arrive gradually: **TXT and Markdown first** (M2, M8), then HTML, then PDF (text layer only, **no OCR**) in M8b. Max 20 MB. |
| D11 | **Frontend: Vite + React + TypeScript, shadcn/ui, TanStack Query** | shadcn/ui components are copied into the repo, so they stay readable and restylable to match `docs/design/` through the design tokens. TanStack Query handles request state and job polling, replacing hand-written loading/error/polling code. Trade-off: Tailwind and Radix become dependencies. |
| D12 | **Python 3.12, uv, ruff, mypy, pytest** | Modern standard tooling; `uv.lock` makes installs reproducible. |
| D13 | **Docker Compose**: `api` (FastAPI/uvicorn) + `web` (nginx serving the Vite build and proxying `/api`) | One command to run. Optional `ollama` service behind a compose profile for a fully local LLM. |

---

## 4. Stack and dependencies

**Backend (`backend/pyproject.toml`)**
- Runtime: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings`, `python-multipart`
- Retrieval: `chromadb`, `bm25s` (+ `PyStemmer`), `sentence-transformers` (CPU `torch`)
- LLM: `openai` (OpenAI-compatible client), `anthropic`
- Parsing: `beautifulsoup4` + `lxml` (EDGAR HTML), `pypdf` (PDF text layer)
- Tokens for chunking: the embedder's own tokenizer (from `sentence-transformers`); no extra library
- HTTP for the fetch script: `httpx`
- Dev: `pytest`, `pytest-asyncio` (only if needed), `ruff`, `mypy`, `types-*` stubs as needed

**Frontend (`frontend/package.json`)**
- `react`, `react-dom`, `vite`, `typescript`, `@vitejs/plugin-react`
- UI: `shadcn/ui` (with what it requires: `tailwindcss`, Radix primitives, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`)
- Server state: `@tanstack/react-query`
- Dev: `eslint` (+ TS plugin), `vitest`, `@testing-library/react`, `jsdom`
- No axios (use `fetch` with a small typed client, called from TanStack Query). No other state library.

---

## 5. Architecture

```
                   ┌─────────────── ingestion (CLI script or upload job) ───────────────┐
 raw file ──▶ loader (html/pdf/txt/md) ──▶ section detection ──▶ chunker ──▶ embedder ──▶ Chroma (text+metadata+vector)
                                                                                     └──▶ rebuild BM25 index from Chroma

 question ──▶ HybridRetriever
                ├─ dense: embed query ──▶ Chroma top-N   (N = 20)
                ├─ sparse: bm25s top-N
                └─ RRF fuse ──▶ top-k passages (k = 6)
           ──▶ relevance gate (D8a) ──▶ prompt builder (numbered passages) ──▶ LLMClient
           ──▶ citation validator (D7) ──▶ AnswerResponse {answer, sources, retrieved, insufficient_evidence}
```

### Core interfaces (sketch: implement with `typing.Protocol`)

```python
class LLMClient(Protocol):
    def complete(self, system: str, messages: Sequence[ChatMessage], *, max_tokens: int) -> str: ...

class Embedder(Protocol):
    dimension: int
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...   # Qwen3 uses a query instruction/prompt; documents don't

class Retriever(Protocol):
    def search(self, query: str, k: int, filters: SearchFilters | None = None) -> list[ScoredPassage]: ...
```

Implementations:
- `llm/openai_compatible.py` → `OpenAICompatibleClient(base_url, api_key, model)`
- `llm/anthropic_client.py` → `AnthropicClient(api_key, model)` (system prompt goes in the `system` parameter)
- `llm/fake.py` → `FakeLLM` (scripted replies, used in tests)
- `llm/factory.py` → `build_llm(settings) -> LLMClient` (match on `settings.llm_provider`)
- `retrieval/embedder.py` → `SentenceTransformerEmbedder`, `FakeEmbedder` (deterministic hash vectors, for tests)
- `retrieval/dense.py`, `retrieval/sparse.py`, `retrieval/fusion.py` (pure function `rrf(rankings, k=60)`), `retrieval/hybrid.py`

### Domain models (`domain/models.py`, frozen dataclasses or Pydantic)

- `Document`: `doc_id` (sha256 of file bytes, which also deduplicates uploads), `title`, `company`, `ticker`,
  `doc_type` (`10-K`, `10-Q`, `8-K`, `earnings_call`, `news`, `other`), `period_end` (date | None),
  `source` (`edgar` | `upload`), `filename`, `ingested_at`
- `Chunk`: `chunk_id` (`{doc_id}:{index}`), `doc_id`, `text`, `section` (e.g. "Item 1A — Risk Factors"),
  `page` (PDF only), `char_start`, `char_end`
- `ScoredPassage`: `chunk`, `document`, `dense_rank`, `sparse_rank`, `rrf_score`, `dense_similarity`

### Chunking

- Split by detected section first (for 10-Ks: regex on `Item\s+\d+[A-C]?\.` headings), then into windows of about
  **400 tokens with 60 overlap**, using the embedder's tokenizer and breaking on sentence/paragraph
  boundaries where possible. Tune these numbers with the eval (M4) and record the results in the README.
- Drop chunks with fewer than ~30 tokens (table-of-contents noise).
- Keep metadata on every chunk; the UI shows filing · section and the citation links depend on it.

### Prompt (`qa/prompt.py`)

- System prompt: answer **only** from the numbered passages; cite every claim as `[n]`; no outside
  knowledge; no investment advice; if the passages don't answer it, reply exactly `INSUFFICIENT_EVIDENCE`.
- **Prompt-injection guard:** passages (uploads especially) are untrusted. Wrap each one in clear
  delimiters (`<passage id="3" source="AAPL 10-K FY2025, Item 1A">…</passage>`) and state that passage text
  is data, never instructions.
- Low temperature (0–0.2) and a `max_tokens` limit, both from settings.

### Citation validation (`qa/citations.py`)

Pure, heavily unit-tested function:
`validate(answer_text, num_passages) -> ValidatedAnswer(text, cited_ids_in_order, dropped_ids)`
- Parse `[n]` and `[n, m]` / `[n][m]` forms.
- Drop ids outside `1..num_passages` (and strip them from the text).
- Renumber the remaining ids consecutively in order of first appearance and rewrite the text to match.
- No valid citations left → `insufficient_evidence`.

---

## 6. API contract (`/api` prefix)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{status, llm_provider, embedder, documents, chunks}` |
| POST | `/api/ask` | Ask a question |
| GET | `/api/documents` | List documents in the library |
| POST | `/api/documents` | Upload one file (multipart: `file`, `company`, `doc_type`, `period_end?`) → `202 {job_id, doc_id}` |
| GET | `/api/jobs/{job_id}` | `{status: queued\|parsing\|embedding\|indexed\|failed, progress: 0-100, error?, chunks?}` |
| DELETE | `/api/documents/{doc_id}` | Optional (stretch): remove a document and rebuild BM25 |

`POST /api/ask` request:
```json
{ "question": "string (3–1000 chars)", "filters": { "tickers": ["AAPL"], "doc_types": ["10-K"] }, "top_k": 6 }
```
Response:
```json
{
  "answer": "Apple relies on outsourcing partners … [1]. …",
  "insufficient_evidence": false,
  "sources": [
    { "id": 1, "doc_id": "…", "title": "Apple Inc. · Form 10-K", "ticker": "AAPL", "doc_type": "10-K",
      "period_end": "2025-09-27", "section": "Item 1A — Risk Factors", "page": null,
      "excerpt": "…", "chunk_id": "…",
      "retrieval": { "dense_rank": 1, "sparse_rank": 3, "rrf_score": 0.0323 } }
  ],
  "retrieved": [ /* all top-k passages, same shape without id, for "retrieved but not cited" */ ],
  "timings_ms": { "retrieval": 0, "generation": 0 }
}
```
Errors: `422` for validation errors (FastAPI default); `413` file too large; `415` unsupported type;
`422` with a clear message for a PDF with no text layer; `502` with a friendly message if the LLM provider fails
(never leak stack traces or keys).

Jobs: an in-memory registry plus FastAPI `BackgroundTasks`, with index writes behind a single `threading.Lock`,
running **one uvicorn worker**. This is a deliberate prototype trade-off; the README must name the production
alternative (a queue such as Celery/RQ/Arq plus a persisted job table).

---

## 7. Configuration (`config.py`, `pydantic-settings`; `.env.example` mirrors it)

```
LLM_PROVIDER=openai_compatible          # openai_compatible | anthropic
LLM_BASE_URL=https://api.groq.com/openai/v1   # or http://ollama:11434/v1, https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=                               # check the provider's current model list
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=                         # check Anthropic's current model list
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=700

EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
EMBEDDING_DEVICE=cpu

DATA_DIR=./data
CHUNK_TOKENS=400
CHUNK_OVERLAP=60
RETRIEVAL_CANDIDATES=20
TOP_K=6
RRF_K=60
MIN_RELEVANCE=0.35                       # tuned in M4; document the chosen value
MAX_UPLOAD_MB=20
CORS_ORIGINS=http://localhost:5173

SEC_USER_AGENT=                          # e.g. "Your Name your@email" (required by SEC EDGAR)
```
Validate on startup: e.g. `anthropic` provider without `ANTHROPIC_API_KEY` → fail fast with a clear message.

---

## 8. Repository structure

```
novabridge-qa/
├── README.md                     # final deliverable (outline in section 11)
├── CLAUDE.md                     # short: "read docs/HANDOFF.md; commands; rules"
├── .env.example
├── .gitignore                    # .env, data/index/, data/uploads/, node_modules/, dist/, .venv/
├── docker-compose.yml            # api, web, optional ollama (profile: local-llm)
├── docs/
│   ├── BRIEF.md                  # the original task text
│   ├── HANDOFF.md                # this file
│   └── design/                   # static HTML designs: the UI reference
│       ├── 01-ask.html
│       ├── 02-answer.html
│       ├── 03-upload.html
│       └── 04-no-evidence.html
├── ai-logs/                      # unedited AI chat exports + README index of what each was used for
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── Dockerfile
│   ├── src/novabridge_qa/
│   │   ├── __init__.py
│   │   ├── main.py               # create_app(): builds the container, routers, CORS
│   │   ├── config.py
│   │   ├── container.py          # wires settings → embedder, stores, retriever, llm, services
│   │   ├── domain/models.py
│   │   ├── api/
│   │   │   ├── schemas.py        # Pydantic request/response models (API layer only)
│   │   │   ├── deps.py           # FastAPI dependencies → container
│   │   │   ├── routes_ask.py
│   │   │   ├── routes_documents.py
│   │   │   └── routes_health.py
│   │   ├── ingestion/
│   │   │   ├── loaders.py        # load_html / load_pdf / load_text → (text, page_spans)
│   │   │   ├── sections.py       # 10-K "Item X" section detection
│   │   │   ├── chunking.py
│   │   │   ├── pipeline.py       # ingest_file(path, meta) -> Document
│   │   │   └── jobs.py           # in-memory job registry
│   │   ├── retrieval/
│   │   │   ├── embedder.py
│   │   │   ├── dense.py          # Chroma wrapper
│   │   │   ├── sparse.py         # bm25s wrapper (build from Chroma, save/load)
│   │   │   ├── fusion.py         # rrf()
│   │   │   └── hybrid.py
│   │   ├── llm/
│   │   │   ├── base.py           # LLMClient Protocol, ChatMessage, LLMError
│   │   │   ├── openai_compatible.py
│   │   │   ├── anthropic_client.py
│   │   │   ├── fake.py
│   │   │   └── factory.py
│   │   └── qa/
│   │       ├── prompt.py
│   │       ├── citations.py
│   │       └── service.py        # QAService.ask(question, filters) -> Answer
│   ├── scripts/
│   │   ├── fetch_filings.py      # download the 10-Ks from EDGAR into data/raw/
│   │   └── ingest.py             # (re)build the index from data/raw/
│   ├── eval/
│   │   ├── questions.jsonl       # ~15–20 hand-written Q → expected doc + section (+ "unanswerable")
│   │   └── run_eval.py           # recall@k / MRR for bm25 vs dense vs hybrid; embedder comparison
│   ├── data/
│   │   ├── raw/                  # committed EDGAR filings + manifest.json (metadata)
│   │   ├── index/                # gitignored: chroma + bm25
│   │   └── uploads/              # gitignored
│   └── tests/
│       ├── conftest.py           # FakeEmbedder, FakeLLM, tmp data dir, TestClient
│       ├── unit/                 # chunking, sections, fusion, citations, prompt, factory, loaders
│       └── api/                  # ask, documents/upload/jobs, health (with fakes)
└── frontend/
    ├── package.json
    ├── vite.config.ts            # dev proxy /api → http://localhost:8000
    ├── tsconfig.json
    ├── Dockerfile                # build → nginx
    ├── nginx.conf                # serve dist/, proxy /api → api:8000, client_max_body_size 20m
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/{client.ts,types.ts}   # types mirror backend schemas
        ├── styles/{tokens.css,global.css}   # tokens feed the shadcn/Tailwind theme variables
        └── components/
            ├── ui/                    # generated shadcn/ui components
            ├── AppShell.tsx
            ├── DocumentLibrary.tsx
            ├── AskForm.tsx
            ├── ExampleQuestions.tsx
            ├── AnswerCard.tsx         # renders [n] as CitationChip links
            ├── CitationChip.tsx
            ├── SourceCard.tsx
            ├── NoEvidenceCard.tsx
            ├── UploadDialog.tsx
            └── UploadQueueItem.tsx
```

### Design reference

`docs/design/*.html` are static mockups. Match them closely:
- Font: **IBM Plex Sans** (UI), **IBM Plex Mono** (tickers, retrieval scores, citation numbers).
- Tokens: background `#F5F4EF`, surface `#FFFFFF`, border `#E2E0D8`, input border `#C9C6BC`, text `#15171C`,
  muted text `#555B66`, accent `#1E3A8A`, citation chip bg `#E8ECF7`, success `#E3F1E7`/`#1F5A33`,
  warning `#FBF1DC`/`#5C3800`, error `#FDF4F2`/`#8A2A1A`, excerpt bg `#F7F6F2`.
- Layout: header, then document library sidebar (stacks above content on narrow screens), then main content.
- Accessibility: real `<button>`/`<a>`/`<label>`, 44 px touch targets, `role="dialog" aria-modal` on upload,
  focus moves into the dialog and returns on close, Escape closes it, citation chips have `aria-label="Source n"`.
- States the UI must handle: empty library, loading (skeleton or spinner on Ask), answer, not enough evidence,
  LLM/network error, upload queue (queued/parsing/embedding with progress/indexed/failed).

---

## 9. Milestones

Each milestone ends with: checks passing, a short summary to Ivan, and his approval.

**M0 — Skeleton & tooling**
`backend/` with uv project, ruff + mypy (strict on `src`) + pytest configured; `config.py`; `main.py` with
`/api/health`; `.env.example`; `.gitignore`; `CLAUDE.md`; `docs/BRIEF.md`; `docs/design/` copied in;
`ai-logs/README.md`. GitHub Actions CI running lint + types + tests.
✅ `uv run uvicorn novabridge_qa.main:create_app --factory` serves `/api/health`; CI is green.

**M1 — Corpus**
`scripts/fetch_filings.py` downloads the latest 10-K for AAPL, MSFT, NVDA from EDGAR (respect `SEC_USER_AGENT`,
rate-limit politely), saves the primary HTML document and writes `data/raw/manifest.json` with metadata.
✅ Files committed; manifest lists company, ticker, form, period end, filing date and source URL.

**M2 — Loading, sections, chunking (TXT first)**
`loaders.py` for TXT/MD only, `sections.py`, `chunking.py`, all unit-tested with synthetic fixtures. HTML and PDF
loaders come later (M8b); keep the loader interface ready for them.
✅ Running the pipeline on the three filings prints a stats table (chunks per doc and section, token distribution);
Ivan spot-checks 5 random chunks.

**M3 — Embedding & dense index**
`Embedder` protocol, `SentenceTransformerEmbedder` (query instruction for Qwen3), `FakeEmbedder`; Chroma wrapper;
`scripts/ingest.py` builds the index idempotently (skip `doc_id`s already indexed).
✅ Ingest is idempotent; a dense-only search for a sample query returns sensible passages.

**M4 — Sparse, fusion, evaluation**
bm25s wrapper (stemming + English stopwords, persisted, rebuildable from Chroma), `rrf()`, `HybridRetriever`
with metadata filters. `eval/questions.jsonl` (Ivan writes or approves every question) and `run_eval.py`
reporting recall@1/3/6 and MRR for bm25 vs dense vs hybrid, and for Qwen3-0.6B vs harrier-0.6b.
Tune `CHUNK_TOKENS`, `TOP_K` and `MIN_RELEVANCE`.
✅ Results table saved to `eval/results.md` and later copied into the README.

**M5 — LLM adapters**
`LLMClient` protocol, `OpenAICompatibleClient`, `AnthropicClient`, `FakeLLM`, `build_llm()` factory;
timeouts, one retry on transient errors, normalized `LLMError`.
✅ Unit tests for the factory and for error normalization (mock the SDK clients); a manual smoke test against
both real providers.

**M6 — QA service: prompt, gate, citations**
`prompt.py`, `citations.py`, `QAService.ask()` implementing D7 and D8.
✅ Extensive unit tests for citation parsing and renumbering; service tests with `FakeLLM` covering:
normal answer, invalid citations dropped, no valid citations → insufficient, retrieval gate → LLM not called,
`INSUFFICIENT_EVIDENCE` reply.

**M7 — API**
`/api/ask`, `/api/documents` (GET), schemas, error handling, CORS, request logging (no question text at INFO
level in production mode).
✅ API tests through `TestClient` with fakes injected via `app.dependency_overrides`; OpenAPI docs look clean.

**M8 — Upload**
`POST /api/documents`, `GET /api/jobs/{id}`, job registry, background ingestion, BM25 rebuild under the
lock, dedup by `doc_id`, size/type validation, a clear error for PDFs with no text.
✅ API tests for success, duplicate, too large, unsupported type and no-text PDF; a manual upload of a real PDF
answers a question about it.

**M8b — HTML and PDF loaders (gradual, one commit each)**
First HTML (BeautifulSoup with scripts/styles/hidden XBRL removed), then PDF (pypdf with page numbers). Add each
to ingestion and to the upload's accepted types.
✅ Loader unit tests with synthetic fixtures; a real file of each format answers a question.

**M9 — Frontend**
Vite + React + TS app with shadcn/ui and TanStack Query (mutations for ask and upload, `refetchInterval` for job
polling), implementing the four designs: library sidebar, ask form with company filter, example
questions, answer with citation chips that scroll to and highlight the source card, "retrieved but not cited"
list, retrieval details toggle, no-evidence card, upload dialog with queue and polling, error states.
✅ `npm run lint && npm run typecheck && npm test` pass (tests at least for `AnswerCard` citation rendering and
`api/client` error handling); manual run of the full flow.

**M10 — Docker & one-command run**
Backend Dockerfile (multi-stage, CPU torch, non-root user, embedding model downloaded at build time or cached
in a volume, with the trade-off noted); frontend Dockerfile (build → nginx); `docker-compose.yml` with
healthchecks, a `data` volume, an ingest-on-first-start step, and an optional `ollama` profile.
✅ On a clean clone: `cp .env.example .env`, set a key, `docker compose up --build`, open
`http://localhost:8080`, ask a question, get a cited answer.

**M11 — README, Swagger docs, logs, final pass**
Finish the Swagger/OpenAPI documentation: summaries, descriptions, request/response examples and documented error
responses on every route. Serve it at `/api/docs` (not FastAPI's default `/docs`) so it works through the nginx
`/api` proxy. Write the README (section 11), export every AI conversation into `ai-logs/` with an index, delete dead code,
make sure no secrets are committed, and do one final clean-clone run.
✅ `/api/docs` is complete and works through nginx; Ivan reviews the README and the whole diff.

**Stretch (only after M11, and only if Ivan asks):** streaming answers (SSE), delete document, a cross-encoder
re-ranker, LLM-as-judge faithfulness eval, filters by period.

---

## 10. Testing strategy

- **Unit:** pure functions (chunking, sections, `rrf`, citation validation, prompt building, settings validation).
- **Service:** `QAService` with `FakeEmbedder` + `FakeLLM` and a tiny in-memory corpus.
- **API:** `TestClient`, dependencies overridden; no network in tests (CI must pass without API keys).
- **Retrieval quality:** `eval/run_eval.py`, run manually; results committed.
- **Frontend:** Vitest + Testing Library for components with logic (citation chips, upload queue state).

---

## 11. README outline (final deliverable)

1. What it is (2–3 sentences) + screenshot
2. Quick start (Docker), then local dev (uv + npm)
3. Configuration (the providers; how to switch between Groq / Ollama / OpenAI / Anthropic)
4. Architecture diagram + request flow
5. Design decisions & trade-offs (D1–D13, condensed), including **why no LlamaIndex**
6. Retrieval evaluation results (the table from M4) and what was tuned
7. How hallucination is limited (prompt, gate, citation validation) and what it still can't guarantee
8. Limitations and what I'd do next for production (queue, auth, persistence, OCR, re-ranking, monitoring)
9. Testing (how to run; what's covered)
10. **AI assistance:** which tools were used for which parts, where the logs are, and notable places where
    generated code was corrected or rejected

---

## 12. Out of scope

Authentication, multi-user data, live market data APIs, agents/tool calling, chat history, OCR,
fine-tuning, cloud deployment.

## 13. AI log requirement (don't forget)

The brief requires the **full, unedited** log of every AI assistant used. At the end of each Claude Code
session, Ivan exports it (`/export`) into `ai-logs/` (e.g. `ai-logs/2026-11-07-claude-code-M0-M2.md`).
The planning conversation in the Claude app (where this handoff and the designs were made) is exported too.
`ai-logs/README.md` lists each log with one line on what it covered.
