import type { AskResponse, Passage, Source } from "@/api/types";

export function makePassage(number: number): Passage {
  return {
    doc_id: "doc",
    title: "ACME Corp · Form 10-K",
    ticker: "ACME",
    doc_type: "10-K",
    period_end: "2025-09-27",
    section: "Item 1 — Business",
    page: null,
    excerpt: `Anvil fact ${number}.`,
    chunk_id: `doc:${number}`,
    retrieval: { dense_rank: number, sparse_rank: null, rrf_score: 0.0323, rerank_rank: number },
  };
}

export function makeSource(id: number): Source {
  return { ...makePassage(id), id };
}

export function makeResponse(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    answer: "ACME sells anvils [1]. They are heavy [2].",
    insufficient_evidence: false,
    sources: [makeSource(1), makeSource(2)],
    retrieved: [makePassage(1), makePassage(2), makePassage(3)],
    timings_ms: { retrieval: 12, generation: 340 },
    ...overrides,
  };
}
