# NovaBridge Q&A on LlamaIndex: design

> Committed on `spike/llamaindex` as found. Its claims were checked against `323773e`; "Corrections found before stage 1" at the end lists where the code has moved since.

Nov 8, 2026 · @Ivan

## Summary

A LlamaIndex version is feasible: about two thirds of today's backend becomes library calls, and the parts that make the system trustworthy survive as LlamaIndex components rather than disappearing. The recommended shape is **LlamaIndex for the plumbing, our domain logic plugged in as LlamaIndex components**.

- **Replaced by LlamaIndex:** the Chroma wrapper, the BM25 wrapper, RRF, the indexing header, the ingestion loop, the LLM adapters and the fake LLM and embedder used in tests.
- **Kept, rewritten as components:** 10-K section detection (a custom `NodeParser`), the relevance gate and citation validation (a `CustomQueryEngine`), and the prompt.
- **Not used, on purpose:** `CitationQueryEngine`, `SimilarityPostprocessor` and the default `QueryFusionRetriever` settings. Each one silently breaks a guarantee we have today (see Traps).

Everything below was checked against the installed source of `llama-index-core` 0.14.25, `llama-index-retrievers-bm25` 0.8.0, `llama-index-vector-stores-chroma` 0.6.0 and `llama-index-embeddings-fastembed` 0.7.0, on the repo as of commit `323773e` (6 filings, 45 answerable questions). Nothing here has been run against the eval yet; the migration plan says how to prove parity.

## Component mapping

Most modules map onto LlamaIndex. The loaders, section detection, the gate and citation checking stay ours, because LlamaIndex has nothing for them or its version would weaken a guarantee.

| Today | LlamaIndex replacement | Verdict |
| --- | --- | --- |
| `ingestion/loaders/*` (TXT, HTML with table rendering) | `Document(text=..., id_=sha256, metadata=...)`; loaders stay ours | Keep. `SimpleDirectoryReader` and `HTMLTagReader` drop our EDGAR markup stripping and table rendering |
| `ingestion/sections.py` | none | Keep, inside a custom `TenKNodeParser` |
| `ingestion/chunking.py` | `SentenceSplitter` (punkt sentences, then regex fallback), called per section by `TenKNodeParser` | Replace, then re-measure |
| `domain.indexed_text` (title + section header) | node `metadata_template`, `metadata_separator`, `text_template`, `excluded_embed_metadata_keys` | Replace. Same string, produced by `MetadataMode.EMBED` |
| `ingestion/pipeline.py`, `uploads._chunk_embed_store` | `IngestionPipeline([TenKNodeParser, embed_model], vector_store=..., docstore=...)` | Replace; upload validation and jobs stay |
| `retrieval/embedder.py` | `BaseEmbedding` subclass wrapping fastembed | Wrap. The stock `FastEmbedEmbedding` drops the bge query prefix |
| `retrieval/dense.py` (Chroma) | `ChromaVectorStore` + `VectorStoreIndex.from_vector_store` + `VectorIndexRetriever` | Replace |
| `retrieval/sparse.py` (bm25s) | `BM25Retriever` (also bm25s + PyStemmer) | Replace, with a zero-score filter |
| `retrieval/fusion.py` + `hybrid.py` | `QueryFusionRetriever(mode="reciprocal_rerank", num_queries=1)` | Replace, subclassed to keep per-retriever ranks and the dense similarity |
| `domain.SearchFilters` | `MetadataFilters` with `FilterOperator.IN` | Replace |
| `qa/service.py` (gate, generate, refuse) | `CustomQueryEngine` | Keep logic, new host |
| `qa/citations.py` | none | Keep verbatim |
| `qa/prompt.py` | `ChatPromptTemplate` | Keep text, new type |
| `llm/*` adapters + `factory.py` | `OpenAILike` (Groq, Ollama), `Anthropic` from `llama-index-llms-*` | Replace; keep a thin error-mapping wrapper |
| `llm/fake.py`, test embedder | `MockLLM` / a `CustomLLM` with scripted replies, `MockEmbedding` | Replace |
| `api/*`, frontend, `eval/*` | unchanged; `run_eval.py` calls the sub-retrievers for dense-only and BM25-only | Keep |

## Target architecture

Every decision about whether to answer (the gate, the model's refusal marker, citation checking) stays in our code; LlamaIndex carries storage, search, fusion and the provider calls.

&#91;embedded content: LlamaIndex architecture · ingestion and question answering\]

At ingest, `IngestionPipeline` runs `TenKNodeParser` and `BgeEmbedding` and writes to `ChromaVectorStore`; a `SimpleDocumentStore` keyed by sha256 skips files already indexed. After each upload, BM25 is rebuilt from `vector_store.get_nodes()` and swapped in, as now. At query time, `HybridRetriever` fuses the two top-20 lists with the library's RRF but keeps dense similarity and both ranks, which the gate, the API's passage cards and `run_eval.py` all need.

## Traps found in the source

Ten defaults would silently change behaviour; nine were confirmed by reading the installed code and the tenth by running the sketch below. The first three would break the relevance gate or add hidden LLM calls.

| # | Where | What the code does | Consequence | Fix |
| --- | --- | --- | --- | --- |
| 1 | `ChromaVectorStore.query` | Reports similarity as `exp(-distance)`, not `1 - distance` | `MIN_RELEVANCE` 0.58 no longer means what was measured. Ranking is unchanged (monotonic) | Convert back: cosine = 1 + ln(score), or re-measure the gate. Pin with a test |
| 2 | `QueryFusionRetriever` | `num_queries` defaults to 4: one LLM call per question to write three extra queries | Hidden cost and latency, and the Groq free-tier budget burns 2x faster | `num_queries=1` |
| 3 | `QueryFusionRetriever._reciprocal_rerank_fusion` | Overwrites each node's score with its RRF score, in place | Dense similarity is gone before the gate runs; `SimilarityPostprocessor(0.58)` after fusion would reject everything (RRF scores are about 0.03) | Subclass and capture dense similarity and both ranks before fusing |
| 4 | `FastEmbedEmbedding._get_query_embedding` | Calls fastembed's `query_embed`, which for bge-small embeds the text as is | The bge query instruction we add today disappears | Small `BaseEmbedding` subclass that adds the prefix |
| 5 | `SentenceSplitter` | Default tokenizer is tiktoken (GPT), not bge's | Chunk sizes counted in the wrong tokens; chunks can pass bge's 512 limit and be truncated | Pass `tokenizer=` the bge tokenizer's `encode` |
| 6 | `SentenceSplitter.split_text_metadata_aware` | Subtracts the metadata header's tokens from `chunk_size` | 400 now means header + text, not text alone | A plus: set `chunk_size` near 460 so header + text stays under 512, then re-measure |
| 7 | `NodeParser` default `id_func` | Random UUID per node | A retry after a crash writes duplicate chunks instead of upserting | `id_func` returning `{sha256}:{i}` |
| 8 | `BM25Retriever._retrieve` | Returns chunks with score 0 (no shared term) | Unrelated chunks earn RRF points when BM25 finds few matches | Subclass that drops scores of 0, as `sparse.py` does today |
| 9 | `BM25Retriever.__init__` | Metadata filters are fixed when the retriever is built | Per-request ticker or source filters are not possible on a shared instance | Build a filtered `BM25Retriever(existing_bm25=...)` per filtered request; cheap at about 1,000 chunks |
| 10 | `QueryFusionRetriever.__init__` | Resolves `Settings.llm` when no `llm` is passed, even with `num_queries=1`; the default is OpenAI | Startup crashes without `OPENAI_API_KEY` on a Groq or Ollama setup | Pass the app's LLM explicitly; never rely on global `Settings` |

Three smaller differences: LlamaIndex RRF counts ranks from 0, so it sums 1/(60 + r) where we sum 1/(61 + r), and k is hard-coded at 60. Fusion deduplicates by content hash rather than chunk id, so the BM25 copy and the Chroma copy of a node must serialize identically (worth a test). And `node_to_metadata_dict` writes its own `doc_id` key into Chroma metadata, set to the ref document id, so our `doc_id` must be the file Document's `id_` or it is overwritten.

Two engines were rejected outright. `CitationQueryEngine` re-splits retrieved passages into 512-token "Source N" pieces with the default tokenizer, may call the LLM several times in refine mode, and never validates citations. `SimpleDirectoryReader` would replace loaders that took real work (EDGAR markup, HTML tables).

## Code sketch

The four components we would own come to about 150 lines, and they run. A smoke test against `llama-index-core` 0.14.25 with a synthetic ACME filing checked that the embedded text equals today's `indexed_text`, that `start_char_idx` slices back to the node text, that dense and BM25 ranks survive fusion, and that the engine returns a renumbered answer (`【2】` and `[1, 9]` become `[1]` and `[2]`), a model refusal and a gate refusal.

**Ingestion: section-aware splitting on top of `SentenceSplitter`.**

```python
class TenKNodeParser(NodeParser):
    """Split at `Item N.` headings, then SentenceSplitter inside each section."""
    chunk_size: int = 460  # header + text, so the whole indexed string fits bge's 512
    chunk_overlap: int = 60
    _splitter: SentenceSplitter = PrivateAttr()

    def __init__(self, tokenizer: Callable[[str], list[int]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._splitter = SentenceSplitter(chunk_size=self.chunk_size,
                                          chunk_overlap=self.chunk_overlap, tokenizer=tokenizer)

    def _parse_nodes(self, nodes, show_progress=False, **kwargs) -> list[BaseNode]:
        out: list[BaseNode] = []
        for doc in nodes:
            text = doc.get_content()
            for section in detect_sections(text):  # ours, unchanged
                header = " · ".join(p for p in (doc.metadata["title"], section.title) if p)
                cursor = section.start
                for piece in self._splitter.split_text_metadata_aware(
                        text[section.start:section.end], header):
                    start = text.find(piece, cursor)
                    cursor = max(start, cursor) + 1
                    node = TextNode(
                        id_=f"{doc.id_}:{len(out)}",  # deterministic, so a retry upserts
                        text=piece, start_char_idx=start, end_char_idx=start + len(piece),
                        metadata={**doc.metadata, "section": section.title or ""},
                        excluded_embed_metadata_keys=[k for k in ALL_KEYS if k not in ("title", "section")],
                        excluded_llm_metadata_keys=list(ALL_KEYS),  # the prompt is built by us
                        metadata_template="{value}", metadata_separator=" · ",
                        text_template="{metadata_str}\n{content}")  # = indexed_text()
                    node.relationships[NodeRelationship.SOURCE] = doc.as_related_node_info()
                    out.append(node)
        return out
```

**Retrieval: library RRF, without losing what the gate and the eval need.** It relies on two private methods, so the LlamaIndex version gets pinned.

```python
class HybridRetriever(QueryFusionRetriever):
    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        results = self._run_sync_queries([query_bundle])  # {(query, retriever index): hits}
        dense, sparse = (results[(query_bundle.query_str, i)] for i in (0, 1))
        info: dict[str, dict[str, Any]] = {}
        for rank, hit in enumerate(dense, start=1):  # read before fusion overwrites scores
            info[hit.node.node_id] = {"dense_rank": rank,
                                      "dense_similarity": 1.0 + math.log(hit.score)}  # Chroma exp(-d)
        for rank, hit in enumerate(sparse, start=1):
            info.setdefault(hit.node.node_id, {})["sparse_rank"] = rank
        fused = self._reciprocal_rerank_fusion(results)[: self.similarity_top_k]
        return [ScoredHit(node=h.node, score=h.score, **info.get(h.node.node_id, {}))
                for h in fused]

class NonZeroBM25Retriever(BM25Retriever):
    def _retrieve(self, query_bundle):
        return [n for n in super()._retrieve(query_bundle) if (n.score or 0) > 0]

retriever = HybridRetriever(
    retrievers=[index.as_retriever(similarity_top_k=20), bm25],  # bm25: similarity_top_k=20
    mode="reciprocal_rerank", num_queries=1, use_async=False,
    llm=llm,  # never called, but omitted means Settings.llm, which is OpenAI
    similarity_top_k=6)
```

**Answering: today's `QAService.ask`, hosted in a `CustomQueryEngine`.** `validate`, `SYSTEM_PROMPT` and `build_user_message` are imported unchanged.

```python
class GroundedQueryEngine(CustomQueryEngine):
    retriever: BaseRetriever
    llm: LLM
    min_relevance: float

    def custom_query(self, query_str: str) -> Response:
        hits = self.retriever.retrieve(query_str)
        sims = [h.dense_similarity for h in hits if h.dense_similarity is not None]
        if not sims or max(sims) < self.min_relevance:
            return Response("", source_nodes=hits, metadata={"refusal": "gate"})
        reply = self.llm.chat([
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=build_user_message(query_str, to_passages(hits)))])
        text = reply.message.content or ""
        if INSUFFICIENT_EVIDENCE in text:
            return Response("", source_nodes=hits, metadata={"refusal": "model"})
        checked = validate(text, len(hits))
        if not checked.cited_ids_in_order:
            return Response("", source_nodes=hits, metadata={"refusal": "no_citations"})
        cited = [hits[i - 1] for i in checked.cited_ids_in_order]
        return Response(checked.text, source_nodes=hits, metadata={"cited": cited, "raw": reply.raw})
```

**Wiring** (not yet run against a real Chroma directory):

```python
collection = chromadb.PersistentClient(path=...).get_or_create_collection(
    "chunks", configuration={"hnsw": {"space": "cosine"}}, metadata={"embedding_model": model})
vector_store = ChromaVectorStore(chroma_collection=collection)
pipeline = IngestionPipeline(
    transformations=[TenKNodeParser(tokenizer=bge_encode), embed_model],
    vector_store=vector_store, docstore=SimpleDocumentStore())  # docstore skips known sha256 ids
index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
bm25 = NonZeroBM25Retriever.from_defaults(nodes=vector_store.get_nodes(), similarity_top_k=20)
llm = OpenAILike(model=..., api_base=..., api_key=..., is_chat_model=True, max_retries=1)  # or Anthropic(...)
```

## Gains, losses and trade-offs

The net code saving is real but smaller than it looks: roughly 700 lines of retrieval, chunking, ingestion and adapter code go, and about 200 lines of LlamaIndex subclasses and wiring arrive. The bigger change is who owns the behaviour.

|  | With LlamaIndex | Today |
| --- | --- | --- |
| Fits the brief's suggested stack | Yes, directly | Needs the D1 justification |
| Code we own | About 200 lines of components, plus the domain modules kept | About 900 lines in `retrieval/`, `ingestion/`, `llm/` |
| New retrievers, re-rankers, vector stores | One-line swaps: `SentenceTransformerRerank`, `QdrantVectorStore`, `PGVectorStore` | Write each adapter |
| Agent extension (prep Q18) | `FunctionAgent` or a Workflow, with the engine as a `QueryEngineTool` | About 200 lines of loop |
| Tracing (prep Q16) | Instrumentation events, Langfuse and OpenTelemetry handlers exist | Add by hand |
| Upload progress bar | Lost by default: `IngestionPipeline.run` has no per-batch callback. Recover with an instrumentation handler on embedding events, or embed outside the pipeline | Built in |
| Behaviour visible in our code | Partly: RRF, splitting and storage format live in the library, and we subclass two private methods | Fully |
| Upgrade risk | Pin `llama-index-core`; any upgrade reruns both evals | None from a framework |
| Dependencies | `llama-index-core` pulls nltk, tiktoken, SQLAlchemy, networkx, aiohttp and the workflows package; about 45 MB for llama\_index, nltk and tiktoken alone | Five focused libraries |
| Chroma storage format | Node JSON in `_node_content` metadata; the current index must be rebuilt | Own schema |
| Typing | Pydantic models with loose return types; `mypy --strict` needs casts or per-module relaxations | Strict throughout |

What does not change: the 10-K section detection, the citation validator, the prompt, the gate and both evals. Those are what the interview will probe, and in both versions they are our code.

## Migration and validation plan

Do it on a branch (`spike/llamaindex`) in stages, so that each stage is measured against `eval/results.md` before the next starts. The bar is parity: hybrid Success@6 and MRR within one question of today on both the TXT (21) and HTM (24) sets, unanswerable refusals 8 of 8, and the gate separating off-topic from answerable as cleanly as 0.58 does now.

1. **LLM layer.** Swap the adapters for `OpenAILike` and `Anthropic` behind a small wrapper that maps provider errors to our `LLMError` messages and reads token usage from `reply.raw`. Tests use a scripted `CustomLLM`. No retrieval change, so the answer eval should not move.
2. **Storage and dense retrieval.** `ChromaVectorStore` + `VectorIndexRetriever`, with the 1 + ln(score) conversion and a test that pins it. Keep our chunker for now (wrap it as a `NodeParser`) so only one thing changes. Re-ingest, then run `run_eval.py`; its dense rows should match exactly.
3. **BM25 and fusion.** `NonZeroBM25Retriever` + `HybridRetriever`. Expect tiny shifts from rank-from-0 RRF and different BM25 tokenization (`\w\w+`). Check hybrid and candidate recall tables.
4. **Chunking.** Switch to `TenKNodeParser` with `SentenceSplitter`, the bge tokenizer and `chunk_size` near 460. Rerun the 200/300/400 sweep, because punkt sentence boundaries and the header-inclusive size both change chunks. Check that `Mr.` and `Ltd.` cuts do not return (`scripts/chunk_stats.py`).
5. **Query engine.** `GroundedQueryEngine` behind the existing `/api/ask` schema; `ScoredHit` maps to `ScoredPassage`, so the API and the frontend do not change. Run the answer eval on Groq, paced for the free tier.
6. **Ingestion and uploads.** `IngestionPipeline` with deterministic node ids and a docstore for sha256 dedup; restore the progress bar with an instrumentation handler. Keep the write lock and the BM25 rebuild-and-swap.
7. **Docs.** Replace D1 in `HANDOFF.md` and the README row, and lift the "no LlamaIndex" rule in `CLAUDE.md` and `IMPROVEMENTS.md`, so a future agent session does not revert it.

Drop the spike if stage 3 or 4 loses more than one question that cannot be explained and fixed; the eval decides, not the framework.

## How to talk about it in the interview

This design turns prep answer Q8 ("Why no LlamaIndex?") from a defence into a demonstration: you know exactly what the framework would replace and where its defaults would have hurt this system.

> "I chose plain Python, but I designed the LlamaIndex version to check that the choice was fair. About 700 lines of retrieval and adapter code would become library calls: `ChromaVectorStore`, `BM25Retriever`, `QueryFusionRetriever` and the LLM integrations. The parts that make answers trustworthy stay mine either way: section detection as a custom node parser, and the gate and citation check in a custom query engine.
>
> Reading the source, I found defaults that would have broken things quietly. The fusion retriever makes an extra LLM call per question unless you set `num_queries=1`. It overwrites the dense similarity with the RRF score, so my relevance gate would have nothing to read. And Chroma's integration reports `exp(-distance)`, so my 0.58 threshold would mean something else. None of those shows up in unit tests with fakes. With the eval in place, I'd be comfortable migrating, stage by stage."

**Follow-ups**

- *"So would you use it in production?"* On a team already on LlamaIndex, yes: its integrations (re-rankers, pgvector, Qdrant, tracing, agents) save more than they cost once the system grows. I'd pin the version and gate upgrades on the eval.
- *"Why not LangChain?"* For retrieval-centred work LlamaIndex has the better primitives (nodes, node parsers, fusion retriever); LangChain or LangGraph fits agent workflows better. The trade-offs would be the same: keep the gate and the validator ours.
- *"What did the source reading cost?"* About an hour, and it found ten behaviour changes. That is the argument for reading what a framework does before adopting it.

The prep doc's numbers are from the 3-filing corpus; the repo now has 6 filings and 45 answerable questions, so refresh them from `eval/results.md` before the interview.

## Corrections found before stage 1

Checked on Nov 9, 2026 against `main` at `83146fa`, before any spike code was written.

1. **The re-ranker is missing.** PR #4 added a cross-encoder after RRF (HANDOFF D14), so production retrieval is RRF to depth `max(k, 20)`, then `FastEmbedReranker`, then top k. The sketched `HybridRetriever` cuts to top k at fusion, which would drop it, and `ScoredHit` has no `rerank_rank` / `rerank_score` for the passage cards. Parity is measured on the reranked rows as well as hybrid.
2. **The gate reads a different set.** Today it checks the best dense similarity over all dense candidates, before fusion and re-ranking (`SearchResult.best_similarity`). The sketched `GroundedQueryEngine` takes the max over the fused top k only, which is stricter. The retriever must report `best_similarity` separately.
3. **`openai<3`.** `llama-index-llms-openai` 0.8.3 (needed by `-openai-like`) requires `openai<3`; `main` locks 3.46.0. The spike downgrades `openai` (approved by Ivan).
4. **Retries stack.** LlamaIndex wraps OpenAI SDK retries in its own tenacity retry (`stop_after_attempt(max_retries)`, default 3). `max_retries=1` gives today's behaviour: one SDK retry, no tenacity retry. A test pins it.

Found while building stage 1 (Nov 9, 2026):

5. **No working Anthropic integration.** `llama-index-llms-anthropic` 0.12.3, the latest release, builds requests with `anthropic.types.MessageParam(...)`. That is a TypedDict up to SDK 1.17 and a `Union` from SDK 2.0, so with SDK 2.x every call raises `TypeError: Cannot instantiate typing.Union`. Downgrading to SDK 1.17 would also change the API version header from `2026-10-21` to `2023-06-01`. Ivan's decision: this branch supports `LLM_PROVIDER=openai_compatible` only (Groq, Ollama, OpenAI), and the comparison with main records Anthropic as lost. Two more defaults in that integration would also have needed overriding: it sends `temperature` unless the model id is in its `ANTHROPIC_NO_TEMP_MODELS` (API 2026-10-21 rejects it on every model), and on every call it raises `ValueError` for a model id missing from its context-window table, because the chat callback reads `metadata`.
6. **Empty `choices`.** The OpenAI integration reads `response.choices[0]` without checking, so a reply with no choices raises `IndexError`. Our wrapper maps it to the existing "returned an empty response" error.

Found while building stage 2 (Nov 9, 2026):

7. **`ChromaVectorStore.add` uses Chroma's `add`, not `upsert`.** A row whose id already exists is kept as it was. With deterministic `{sha256}:{i}` ids and node 0 written last, a retry after a crash still adds exactly what is missing; a test crashes the second batch and retries.
8. **`get_nodes(node_ids=[])` returns every node**, because an empty list becomes "no filter". `ChunkStore.get` returns early on an empty list.
9. **`NodeParser` post-processing.** By default it merges the parent document's metadata into each node (putting the document's keys first) and overwrites `start_char_idx` with its own `text.find()`. Our parser sets `include_metadata=False` and keeps offsets in its own `char_start` / `char_end` metadata.
10. **Indexes are not interchangeable with main.** Nodes are stored as JSON in `_node_content`. `ChunkStore` refuses an index written on main (`IndexFormatError`), because ingestion would otherwise skip its documents as already indexed. Each branch needs its own `data/index`.
11. **`run_eval.py` read the store directly** for the gate table. It now asks the retriever for `best_similarity` in dense mode: the value the gate checks.


Found while building stage 3 (Nov 9, 2026):

12. **`pystemmer<3`.** `llama-index-retrievers-bm25` 0.8.0 pins `pystemmer<3`; `main` locks 3.1.0. The spike keeps 3.1.0 through a uv `override-dependencies` entry (approved by Ivan). The BM25 tests cover the stemmer.
13. **`QueryFusionRetriever` defaults.** `num_queries` defaults to 4, which makes one LLM call per question to write three more queries. When no `llm` is passed it falls back to `Settings.llm`, which is OpenAI. The spike sets `num_queries=1` and passes an LLM that raises if called.
14. **Fusion overwrites scores in place.** After RRF, a hit's dense similarity and its rank in each list are lost, and the gate, the passage cards and the eval need all three. `RankKeepingFusionRetriever` records them before fusing. It calls two private methods, which is one more reason `llama-index-core` is pinned exactly.
15. **RRF constant.** LlamaIndex counts ranks from 0 and fixes k at 60, so a hit scores `1/(60+r)`; `main` scored `1/(61+r)`. Order is unchanged on the eval set. `RRF_K` is now validated to be 60, because the setting can no longer change anything.
16. **`BM25Retriever` edge cases.**
    - It returns hits with a score of 0, including chunks masked out by a filter. They are dropped, because RRF would still score them by rank.
    - It raises `ValueError` on an empty corpus, and again when a filter leaves no node. Both cases are checked against Chroma first.
    - Filters are fixed when the retriever is built, so each filtered request uses a copy that shares the index.
    - When the index is built in memory rather than loaded, `bm25.corpus` is `None`, and a filtered copy then ignores the filter. The subclass fills it in.

Stage 3 eval: every recall, MRR, candidate-recall, miss and gate row in `eval/results.md` is identical to `main`. Only the latencies differ, within run-to-run noise.
