"""LlamaIndex version of NovaBridge Q&A: the pieces that are ours."""

import math
from collections.abc import Callable, Sequence
from typing import Any

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.response.schema import Response
from llama_index.core.llms import LLM, ChatMessage
from llama_index.core.node_parser import NodeParser, SentenceSplitter
from llama_index.core.query_engine import CustomQueryEngine
from llama_index.core.retrievers import BaseRetriever, QueryFusionRetriever
from llama_index.core.schema import (
    BaseNode,
    Document,
    NodeRelationship,
    NodeWithScore,
    QueryBundle,
    TextNode,
)
from llama_index.retrievers.bm25 import BM25Retriever
from pydantic import PrivateAttr

from novabridge_qa.ingestion.sections import detect_sections
from novabridge_qa.qa.citations import validate
from novabridge_qa.qa.prompt import INSUFFICIENT_EVIDENCE, SYSTEM_PROMPT, build_user_message

# Shown to the embedder and BM25 only, as "title · section\ntext" (today's indexed_text).
EMBED_KEYS = ("title", "section")
ALL_KEYS = ("title", "section", "company", "ticker", "doc_type", "period_end", "source",
            "filename", "doc_id")


# ---------- ingestion ----------

class TenKNodeParser(NodeParser):
    """Split at `Item N.` headings, then SentenceSplitter inside each section."""

    chunk_size: int = 460  # header + text, so the whole indexed string fits bge's 512
    chunk_overlap: int = 60
    _splitter: SentenceSplitter = PrivateAttr()

    def __init__(self, tokenizer: Callable[[str], list[int]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._splitter = SentenceSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap, tokenizer=tokenizer
        )

    def _parse_nodes(
        self, nodes: Sequence[BaseNode], show_progress: bool = False, **kwargs: Any
    ) -> list[BaseNode]:
        out: list[BaseNode] = []
        for doc in nodes:
            text = doc.get_content()
            for section in detect_sections(text):
                body = text[section.start:section.end]
                header = " · ".join(p for p in (doc.metadata["title"], section.title) if p)
                cursor = section.start
                for piece in self._splitter.split_text_metadata_aware(body, header):
                    start = text.find(piece, cursor)
                    cursor = max(start, cursor) + 1
                    node = TextNode(
                        id_=f"{doc.id_}:{len(out)}",  # deterministic: retries upsert
                        text=piece,
                        start_char_idx=start,
                        end_char_idx=start + len(piece),
                        metadata={**doc.metadata, "section": section.title or ""},
                        excluded_embed_metadata_keys=[k for k in ALL_KEYS if k not in EMBED_KEYS],
                        excluded_llm_metadata_keys=list(ALL_KEYS),
                        metadata_template="{value}",
                        metadata_separator=" · ",
                        text_template="{metadata_str}\n{content}",
                    )
                    node.relationships[NodeRelationship.SOURCE] = doc.as_related_node_info()
                    out.append(node)
        return out


class BgeEmbedding(BaseEmbedding):
    """fastembed bge-small with the query instruction the stock integration leaves out."""

    _model: Any = PrivateAttr()
    _prefix: str = PrivateAttr()

    def __init__(self, model_name: str, prefix: str, **kwargs: Any) -> None:
        super().__init__(model_name=model_name, **kwargs)
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name)
        self._prefix = prefix

    def _get_query_embedding(self, query: str) -> list[float]:
        return next(iter(self._model.embed([self._prefix + query]))).tolist()

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embeddings([text])[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts)]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)


# ---------- retrieval ----------

class NonZeroBM25Retriever(BM25Retriever):
    """bm25s returns chunks that share no term with the query; drop them, as sparse.py does."""

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        return [n for n in super()._retrieve(query_bundle) if (n.score or 0) > 0]


def chroma_cosine(score: float) -> float:
    """ChromaVectorStore reports exp(-distance); the gate was measured on 1 - distance."""
    return 1.0 + math.log(score)


class HybridRetriever(QueryFusionRetriever):
    """Library RRF, but keeps what the API, the gate and the eval need before scores are lost."""

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        results = self._run_sync_queries([query_bundle])  # {(query, retriever index): hits}
        dense, sparse = (results[(query_bundle.query_str, i)] for i in (0, 1))
        info: dict[str, dict[str, Any]] = {}
        for rank, hit in enumerate(dense, start=1):
            info[hit.node.node_id] = {
                "dense_rank": rank, "dense_similarity": chroma_cosine(hit.score or 1e-9)
            }
        for rank, hit in enumerate(sparse, start=1):
            info.setdefault(hit.node.node_id, {})["sparse_rank"] = rank
        fused = self._reciprocal_rerank_fusion(results)[: self.similarity_top_k]
        # Kept on the hit, not in node.metadata, so it never leaks into the indexed or prompt text.
        return [_annotate(hit, info.get(hit.node.node_id, {})) for hit in fused]


class ScoredHit(NodeWithScore):
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_similarity: float | None = None


def _annotate(hit: NodeWithScore, extra: dict[str, Any]) -> ScoredHit:
    return ScoredHit(node=hit.node, score=hit.score, **extra)


def build_retriever(
    vector_retriever: BaseRetriever, bm25: BM25Retriever, llm: LLM, top_k: int
) -> HybridRetriever:
    return HybridRetriever(
        retrievers=[vector_retriever, bm25],
        mode="reciprocal_rerank",
        num_queries=1,       # default 4 = an extra LLM call per question
        use_async=False,
        llm=llm,             # never called with num_queries=1, but omitted = Settings.llm = OpenAI
        similarity_top_k=top_k,
    )


# ---------- answering ----------

class GroundedQueryEngine(CustomQueryEngine):
    retriever: BaseRetriever
    llm: LLM
    min_relevance: float
    to_passages: Callable[[Sequence[ScoredHit]], Sequence[Any]]  # nodes -> ScoredPassage

    def custom_query(self, query_str: str) -> Response:
        hits: list[ScoredHit] = self.retriever.retrieve(query_str)  # type: ignore[assignment]
        sims = [h.dense_similarity for h in hits if h.dense_similarity is not None]
        if not sims or max(sims) < self.min_relevance:
            return Response("", source_nodes=hits, metadata={"refusal": "gate"})

        reply = self.llm.chat([
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(role="user", content=build_user_message(query_str, self.to_passages(hits))),
        ])
        text = reply.message.content or ""
        if INSUFFICIENT_EVIDENCE in text:
            return Response("", source_nodes=hits, metadata={"refusal": "model"})

        checked = validate(text, len(hits))
        if not checked.cited_ids_in_order:
            return Response("", source_nodes=hits, metadata={"refusal": "no_citations"})
        cited = [hits[i - 1] for i in checked.cited_ids_in_order]
        return Response(checked.text, source_nodes=hits, metadata={"cited": cited, "raw": reply.raw})


def make_document(text: str, sha256: str, meta: dict[str, Any]) -> Document:
    # Chroma rejects None; and our doc_id must equal id_, since node_to_metadata_dict overwrites it.
    clean = {k: v for k, v in meta.items() if v is not None}
    return Document(text=text, id_=sha256, metadata={**clean, "doc_id": sha256})
