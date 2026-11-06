"""Question answering endpoint."""

import logging

from fastapi import APIRouter

from novabridge_qa.api.deps import QAServiceDep
from novabridge_qa.api.schemas import (
    AskRequest,
    AskResponse,
    ErrorResponse,
    PassageResponse,
    RetrievalInfo,
    SourceResponse,
    Timings,
)
from novabridge_qa.domain.models import ScoredPassage, SearchFilters
from novabridge_qa.qa.service import Source

logger = logging.getLogger(__name__)

router = APIRouter(tags=["questions"])


def _passage_fields(passage: ScoredPassage) -> dict[str, object]:
    document, chunk = passage.document, passage.chunk
    return {
        "doc_id": document.doc_id,
        "title": document.title,
        "ticker": document.ticker,
        "doc_type": document.doc_type,
        "period_end": document.period_end,
        "section": chunk.section,
        "page": chunk.page,
        "excerpt": chunk.text,
        "chunk_id": chunk.chunk_id,
        "retrieval": RetrievalInfo(
            dense_rank=passage.dense_rank,
            sparse_rank=passage.sparse_rank,
            rrf_score=passage.rrf_score,
        ),
    }


def _to_source(source: Source) -> SourceResponse:
    return SourceResponse.model_validate({"id": source.id, **_passage_fields(source.passage)})


def _to_filters(request: AskRequest) -> SearchFilters | None:
    if request.filters is None:
        return None
    return SearchFilters(
        tickers=tuple(request.filters.tickers),
        doc_types=tuple(request.filters.doc_types),
        sources=tuple(request.filters.sources),
    )


# A plain `def`, so FastAPI runs it in a thread: an `async def` would block the event loop while
# waiting for the embedder and the LLM.
@router.post(
    "/ask",
    summary="Ask a question",
    responses={502: {"model": ErrorResponse, "description": "The LLM provider failed."}},
)
def ask(request: AskRequest, service: QAServiceDep) -> AskResponse:
    # Questions can reveal client work, so they stay out of logs in production.
    logger.debug("Question: %s", request.question)
    answer = service.ask(request.question, _to_filters(request), request.top_k)
    return AskResponse(
        answer=answer.text,
        insufficient_evidence=answer.insufficient_evidence,
        sources=[_to_source(source) for source in answer.sources],
        retrieved=[
            PassageResponse.model_validate(_passage_fields(passage)) for passage in answer.retrieved
        ],
        timings_ms=Timings(retrieval=answer.retrieval_ms, generation=answer.generation_ms),
    )
