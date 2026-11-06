// These mirror backend/src/novabridge_qa/api/schemas.py.

export type DocType = "10-K" | "10-Q" | "8-K" | "earnings_call" | "news" | "other";
export type DocSource = "edgar" | "upload";
export type JobStatus = "queued" | "parsing" | "embedding" | "indexed" | "failed";

export interface Health {
  status: "ok";
  llm_provider: string;
  embedder: string;
  documents: number;
  chunks: number;
}

export interface LibraryDocument {
  doc_id: string;
  title: string;
  company: string;
  ticker: string | null;
  doc_type: DocType;
  period_end: string | null;
  source: DocSource;
  filename: string;
  ingested_at: string;
  chunks: number;
}

export interface AskFilters {
  tickers?: string[];
  doc_types?: DocType[];
  sources?: DocSource[];
}

export interface AskRequest {
  question: string;
  filters?: AskFilters;
  top_k?: number;
}

export interface Passage {
  doc_id: string;
  title: string;
  ticker: string | null;
  doc_type: DocType;
  period_end: string | null;
  section: string | null;
  page: number | null;
  excerpt: string;
  chunk_id: string;
  retrieval: {
    dense_rank: number | null;
    sparse_rank: number | null;
    rrf_score: number;
  };
}

export interface Source extends Passage {
  id: number;
}

export interface AskResponse {
  answer: string;
  insufficient_evidence: boolean;
  sources: Source[];
  retrieved: Passage[];
  timings_ms: { retrieval: number; generation: number };
}

export interface UploadTags {
  company: string;
  doc_type: DocType;
  period_end: string;
}

export interface UploadResponse {
  job_id: string;
  doc_id: string;
}

export interface Job {
  status: JobStatus;
  progress: number;
  error: string | null;
  chunks: number | null;
}
