# Pending improvements

Work through these in order. Each task is written so an agent can start it cold.

## Rules for every task

- Read `CLAUDE.md` and `docs/HANDOFF.md` first. Their rules apply: no LangChain or LlamaIndex, no
  secrets in the repo, no invented facts in fixtures or docs, and ask Ivan before adding a dependency
  that section 4 of the handoff does not list.
- One task per branch, with small conventional commits. Run both check commands from `CLAUDE.md`
  before each commit.
- Measure, do not assume. Retrieval changes are judged with `backend/eval/run_eval.py` (and with the
  answer eval from task 2 once it exists). Put before-and-after numbers in the pull request.
- Run the real flow, not only the tests. Fakes have hidden real bugs here before: the `【1】` citation
  format, the dialog focus and the dark-mode styles were all missed by passing tests.
- Mind the LLM budget. Groq's free tier allows about 8,000 tokens a minute and also has a daily cap.
  A question costs about 3,000 tokens, so pace real-model runs and do not burn the cap on retries.
- Update `README.md` when behaviour, limitations or numbers change.

## Checklist

- [x] 1. HTML loader, and index the 2026 10-Ks (M8b, part 1). Branch `feat/html-loader`. Ivan
      approved the new questions and tried them in the UI.
- [x] 2. End-to-end answer evaluation. Branch `feat/answer-eval`. A `--repeat` option for several
      runs is left for later.
- [ ] 3. Every figure in an answer must appear in a passage it cites
- [ ] 4. Cross-encoder re-ranker
- [ ] 5. Embedder comparison (M8c)
- [ ] 6. Streaming answers over SSE
- [ ] 7. Highlight the exact supporting sentence
- [ ] 8. PDF loader (M8b, part 2)
- [ ] 9. A separate database for production, such as pgvector, keeping our BM25
- [ ] 10. LLM-as-judge

---

## 1. HTML loader, and index the 2026 10-Ks

**Why:** the library only holds the fiscal 2000–2001 filings in plain text. The current 10-Ks are
already in `backend/data/raw/` as `.htm` files but are skipped, because no loader reads them.

**Scope:**
- `load_html` in `ingestion/loaders.py`, using BeautifulSoup with `lxml` (both listed in section 4).
  Remove scripts, styles and hidden content. These are inline XBRL filings, so the `ix:header` block
  and anything with `display:none` must go, or tagging data ends up in passages.
- Turn tables into text rows that keep their columns readable. A known weakness is that a table's
  header can land in a different chunk from its rows. At least do not make it worse, and note
  whether it improves.
- Check that section detection finds the Items in the HTML text, as it does for TXT.
- Add `.html` and `.htm` to the upload's accepted types, in the backend and in the frontend
  (`ACCEPTED` and the help text in `UploadDialog.tsx`).
- Fix the company names in `data/raw/manifest.json`: "MICROSOFT CORP" and "NVIDIA CORP" are in
  capitals, beside "Apple Inc.". Re-ingest afterwards, because names are stored in the index.

**The evaluation needs new questions.** All 29 questions in `eval/questions.jsonl` are about the old
filings. Write questions for the 2026 filings in the same format, and check every answer and
evidence pattern against the filing text. Also write questions that are unanswerable from them. Ivan
approves the questions before they are used for tuning.

**Decide:** both generations will be indexed, so "Apple's latest revenue" becomes ambiguous. Either
keep both and rely on the period in the answer, or let the user filter by period. Write the choice
down.

**Done when:**
- Loader unit tests with synthetic HTML fixtures pass: hidden XBRL is gone, tables are readable, and
  the Items are found.
- All six filings are indexed, `run_eval.py` runs on the new questions, and the numbers are in
  `eval/results.md`.
- A real question about a 2026 10-K gets a cited answer in the browser.
- The example questions in `ExampleQuestions.tsx` and the README's limitations reflect the new
  corpus.

---

## 2. End-to-end answer evaluation

**Why:** `run_eval.py` measures retrieval only. The answer-level numbers in the README come from a
one-off script that is not in the repository, checked by pattern rather than by reading.

**Scope:** a repeatable script, `eval/run_answer_eval.py`, that runs every question through
`QAService` with the real LLM and reports:
- **Answered:** answerable questions that got an answer.
- **Correct:** the answer contains the expected fact. Add an expected-answer field to the questions
  file, as text or a pattern, checked against the filing.
- **Evidence cited:** the passage with the evidence is among the sources.
- **Correct refusals:** unanswerable questions that got no answer, split into refused by the gate
  and refused by the model.
- **Figure check:** sentences flagged by task 3, once it exists.
- Latency and tokens used.

It must pace itself under the rate limit, save raw outputs so a run can be read again without
re-asking, and write a results file to commit.

**Done when:** a run on both corpora is committed, and the README's evaluation section uses it
instead of the one-off numbers.

---

## 3. Every figure in an answer must appear in a passage it cites

**Why:** citation validation proves that a cited passage was retrieved, not that it supports the
sentence. A deterministic check on figures closes the most damaging case for financial answers: a
number with a citation that does not contain it.

**Rule:** split the answer into sentences. For each figure in a sentence, at least one passage cited
by that sentence must contain the same figure. Otherwise the sentence is flagged or dropped.

**The hard part is matching figures.** Real outputs from this project show the problems:
- `gpt-oss` wrote "4 ¾ % per annum (i.e., 4.75% per year)". The passage says "4 3/4%", so the model's
  own conversion to 4.75% is not in it.
- "forty‑two" was written with a non-breaking hyphen, and the passage may spell the number as a
  word.
- "$7.983 billion" may come from a table that reads "7,983" under "(in millions)".

Normalize where it is safe: currency symbols, thousands separators, unicode hyphens and spaces, and
fractions. Do not guess scale from units ("billion" against a table "in millions") without a test
that proves the match is right. A figure that cannot be matched should count as unsupported, not as
passed.

**Decide, with Ivan:**
- Flag or drop. Flagging shows the sentence with a warning in the UI. Dropping removes it, and if
  nothing is left the answer becomes insufficient evidence, as with zero valid citations today.
  Recommendation: flag in the UI, and keep drop as a setting.
- Which numbers count. Years such as "fiscal 2001" and Item numbers should probably not.

**Scope:**
- Backend: the check in `qa/`, a per-sentence result in the response (add it to the API contract in
  the handoff), and a log warning for each failure, without the question text.
- Frontend: show a flagged sentence in a way that is clear but not alarming.
- A unit test for each real case above, and for sentences without figures, figures cited to the
  wrong passage, and sentences with several citations.

**Done when:** the eval's answers are run through the check, and the README's "what this cannot
guarantee" section is updated with what it now catches and what it still misses.

**Related:** task 7 needs the same sentence-to-citation mapping, so build it to be reused.

---

## 4. Cross-encoder re-ranker

**Why:** RRF only combines two rankings. A cross-encoder reads the question and the passage
together, which usually ranks the evidence higher. Hybrid R@1 is 0.52 today, so the answer is often
in the top 6 but not first. Three questions are missed completely (a01, m02, n04), and a re-ranker
cannot help those unless the passage is among the candidates.

**Research first.** Do not assume `bge-reranker-base` is the best choice. Compare candidates on:
- CPU latency for re-ranking 20–40 passages of about 400 tokens, measured on this machine.
- Model size and memory, because it ships in the Docker image.
- Maximum input length against our chunk size.
- License.
- Whether it runs on ONNX through `fastembed` (it has a cross-encoder interface), which would avoid
  bringing `torch` back into the image. Check this in the current `fastembed` release.

Candidates to check include `BAAI/bge-reranker-base`, `BAAI/bge-reranker-v2-m3`, a small MS MARCO
MiniLM cross-encoder and the Jina rerankers. Verify the current model names and availability rather
than trusting this list.

**Scope:**
- A `Reranker` protocol with a fake for tests, like `Embedder`. Re-rank the RRF candidates and keep
  the top `TOP_K`. Make the number of candidates to re-rank a setting.
- The relevance gate uses dense similarity. Decide whether the re-ranker score should replace it,
  and retune the threshold if so.
- Show the re-ranker rank in the retrieval details in the UI and the API.

**Done when:** `run_eval.py` reports with and without re-ranking, the added latency is measured, and
the decision is recorded in `eval/decisions.md`, including "not worth it" if that is the result.

---

## 5. Embedder comparison (M8c)

**Why:** `bge-small-en-v1.5` was chosen to get the system working. Dense search alone has an R@6 of
0.76 at 400 tokens.

**Scope:**
- Compare `bge-small-en-v1.5` (fastembed), `Qwen/Qwen3-Embedding-0.6B` and harrier-0.6b with
  `run_eval.py`, each with its own index. Find harrier's exact model repository name first.
- `SentenceTransformerEmbedder` exists for this. Install it with
  `uv sync --extra sentence-transformers` in `backend/`. It forces float32, because bfloat16 measured
  10 times slower on CPU.
- These models accept longer inputs than 512 tokens, so a larger `CHUNK_TOKENS` is worth trying with
  them.
- Retune `MIN_RELEVANCE` for the winner, since similarity scales differ between models.

**Consider the cost of winning.** If the winner needs `torch`, the Docker image grows by roughly
1.5 GB again (it was 2.57 GB with `torch`, and is 1.06 GB without). Check whether the winner has an
ONNX or `fastembed` version. Record indexing time and query latency, not only recall.

**Done when:** a comparison table is in `eval/results.md` and D4 in the handoff records the final
choice and why.

---

## 6. Streaming answers over SSE

**Why:** the answer appears all at once after generation. Streaming shows text within a second or so.

**This conflicts with server-side checking.** Citations are validated and renumbered after the whole
answer exists (D7), and task 3 checks every sentence. Streamed text cannot be checked before it is
sent. Choose one, and write the choice into D7:
- Stream the raw text as a preview, then send a final event with the checked answer that replaces
  it. Simple, but the user may see a citation or sentence disappear.
- Buffer by sentence and send each sentence once it is checked. No visible correction, but a less
  smooth stream, and renumbering needs care because numbers are assigned in order of first use.

**Scope:**
- A streaming method on both LLM adapters and on `FakeLLM`.
- A new endpoint that keeps `/api/ask` working. `EventSource` only does GET, so the frontend needs
  `fetch` with a stream reader. Send events for retrieval, text, the final answer and errors.
- The relevance gate can answer at once without calling the LLM.
- nginx buffers proxied responses by default, which would hold the stream back. Turn buffering off
  for this location only.
- Errors mid-stream must still give the friendly message, and must not leak provider text.

**Done when:** API tests cover the event order and an error mid-stream, and the answer streams
through nginx in the browser.

---

## 7. Highlight the exact supporting sentence

**Why:** a source card shows the whole chunk of about 400 tokens, so the analyst has to find the
supporting sentence themselves.

**Scope:**
- For each cited sentence of the answer, find the sentence in the passage that best supports it.
  Start with something deterministic: shared figures (from task 3) and word overlap. Embedding
  similarity with the existing embedder is the fallback. Do not ask the LLM for quotes unless the
  deterministic approach measurably fails.
- Return the matching character ranges in the API, and highlight them in `SourceCard.tsx`, scrolling
  the passage to the highlight. Clicking a citation already scrolls to its card.
- Keep the whole chunk available.

**Done when:** the highlight is right on a sample of the eval's real answers, checked by reading, and
the misses are written down.

---

## 8. PDF loader (M8b, part 2)

**Scope:**
- `load_pdf` with `pypdf` (listed in section 4), filling `page_spans` so that chunks get page numbers.
  The frontend already shows a page when one exists.
- A PDF with no text layer (a scanned PDF) gets a 422 with a clear message. The upload path already
  rejects files with no text, so add the PDF case and its API test. That test moved here from M8.
- Add `.pdf` to the accepted types and the upload's help text. OCR stays out of scope.

**Decide, with Ivan:** which real PDF to test with. It must be one that can be committed or at least
used, as SEC filings are mostly HTML.

**Done when:** loader unit tests with a synthetic PDF pass, the no-text 422 test passes, and a real PDF
uploaded in the browser answers a question with the right page number.

---

## 9. A separate database for production, such as pgvector, keeping our BM25

**Why:** Chroma runs embedded, so one process at a time. That is why ingest runs before the API, why
uvicorn has one worker, and why jobs live in memory. A production system needs several workers and
durable state.

**Write the plan first, in `docs/`, and get Ivan's approval before coding.** It should cover:
- The source of truth: Postgres holds the chunks, metadata and vectors. BM25 stays our own code, but
  is rebuilt from Postgres. Several workers each need the BM25 index, so decide whether each one
  builds it, loads it from shared storage, or rebuilds when told that the data changed.
- The `DenseIndex` interface. It is a concrete class today, so extract a protocol and keep Chroma as
  the default for local runs.
- Metadata filters, which become SQL. Also the vector index type and distance, kept as cosine.
- Persisted jobs and a real queue (the README names Celery, RQ or Arq), because in-memory jobs are
  lost on restart.
- Docker Compose with a `postgres` service and migrations.
- New dependencies, such as a Postgres driver and the pgvector adapter, need Ivan's approval.

**Done when:** the same eval numbers come out of both stores, and the app runs with more than one
worker.

---

## 10. LLM-as-judge

**Why:** task 2 checks facts by pattern, which cannot judge whether an answer is faithful to its
sources overall, or whether a refusal was right.

**Scope:**
- A judge step in the answer evaluation that scores faithfulness (every claim is supported by its
  cited passages) and relevance, with a short reason.
- Use a different model from the one that writes the answers, so it does not grade its own work.
- Calibrate it before trusting it: compare its grades with hand grades on about 20 answers, and
  report how often they agree.
- It runs in evaluation only, never on users' requests, so it adds no latency to the app.

**Note:** task 3 already catches unsupported figures deterministically. The judge is for what rules
cannot catch, so it should not replace the figure check.

**Done when:** the judge's scores and its agreement with the hand grades are in the evaluation
results.

---

## Other open items

Smaller things found along the way, to fit in where convenient:

- [ ] Commit the full Claude Code log. The `/export` was taken after the session was compacted, so
      the raw transcript (`.jsonl`) is needed too. Check both for secrets before committing.
- [ ] Ivan approves `eval/questions.jsonl` and spot-checks chunks.
- [ ] Run the Anthropic adapter against the real API once keys are available. The README says it
      has not been run.
- [ ] Run the Ollama profile with a real model. Only its compose configuration was checked.
- [ ] Uploads have no ticker, so they only appear under "My uploads". Add an optional ticker field
      to the upload, or match the company name to a known ticker.
- [ ] CI does not build the Docker images, so a broken Dockerfile would pass. Add a build job.
- [ ] A clean-clone `docker compose up --build` failed once, and the error was not kept. Three
      later builds passed. Keep the log if it happens again.
- [ ] On the home screen, the disclaimer is left-aligned rather than in the centred column.
- [ ] The HTML loader drops empty table cells, so a row with gaps shifts its later cells into the
      wrong columns. Found by the answer eval (`a25`, see `backend/eval/decisions.md`). Keep the
      columns aligned, for example by dropping only columns that are empty in every row.
