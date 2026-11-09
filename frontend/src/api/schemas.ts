// Runtime schemas for the API's responses. They mirror backend/src/novabridge_qa/api/schemas.py,
// and the response types in types.ts are inferred from them, so the two cannot disagree.
import { z } from "zod";

export const DocTypeSchema = z.enum(["10-K", "10-Q", "8-K", "earnings_call", "news", "other"]);
export const DocSourceSchema = z.enum(["edgar", "upload"]);
export const JobStatusSchema = z.enum(["queued", "parsing", "embedding", "indexed", "failed"]);

export const HealthSchema = z.object({
  status: z.literal("ok"),
  llm_provider: z.string(),
  embedder: z.string(),
  documents: z.number(),
  chunks: z.number(),
});

export const ClientConfigSchema = z.object({
  upload_types: z.array(z.string()),
  max_upload_mb: z.number(),
});

export const LibraryDocumentSchema = z.object({
  doc_id: z.string(),
  title: z.string(),
  company: z.string(),
  ticker: z.string().nullable(),
  doc_type: DocTypeSchema,
  period_end: z.string().nullable(),
  source: DocSourceSchema,
  filename: z.string(),
  ingested_at: z.string(),
  chunks: z.number(),
});

export const PassageSchema = z.object({
  doc_id: z.string(),
  title: z.string(),
  ticker: z.string().nullable(),
  doc_type: DocTypeSchema,
  period_end: z.string().nullable(),
  section: z.string().nullable(),
  page: z.number().nullable(),
  excerpt: z.string(),
  chunk_id: z.string(),
  retrieval: z.object({
    dense_rank: z.number().nullable(),
    sparse_rank: z.number().nullable(),
    rrf_score: z.number(),
    /** Rank after cross-encoder re-ranking; null when re-ranking is off. */
    rerank_rank: z.number().nullable(),
  }),
});

export const SourceSchema = PassageSchema.extend({ id: z.number() });

export const AskResponseSchema = z.object({
  answer: z.string(),
  insufficient_evidence: z.boolean(),
  sources: z.array(SourceSchema),
  retrieved: z.array(PassageSchema),
  timings_ms: z.object({ retrieval: z.number(), generation: z.number() }),
});

export const UploadResponseSchema = z.object({
  job_id: z.string(),
  doc_id: z.string(),
});

export const JobSchema = z.object({
  status: JobStatusSchema,
  progress: z.number(),
  error: z.string().nullable(),
  chunks: z.number().nullable(),
});
