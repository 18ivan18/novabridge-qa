// Response types are inferred from the runtime schemas in schemas.ts. Request types are written
// here: the client builds them, so there is nothing to check at runtime.
import type { z } from "zod";

import type {
  AskResponseSchema,
  ClientConfigSchema,
  DocSourceSchema,
  DocTypeSchema,
  HealthSchema,
  JobSchema,
  JobStatusSchema,
  LibraryDocumentSchema,
  PassageSchema,
  SourceSchema,
  UploadResponseSchema,
} from "./schemas";

export type DocType = z.infer<typeof DocTypeSchema>;
export type DocSource = z.infer<typeof DocSourceSchema>;
export type JobStatus = z.infer<typeof JobStatusSchema>;

export type Health = z.infer<typeof HealthSchema>;
export type ClientConfig = z.infer<typeof ClientConfigSchema>;
export type LibraryDocument = z.infer<typeof LibraryDocumentSchema>;
export type Passage = z.infer<typeof PassageSchema>;
export type Source = z.infer<typeof SourceSchema>;
export type AskResponse = z.infer<typeof AskResponseSchema>;
export type UploadResponse = z.infer<typeof UploadResponseSchema>;
export type Job = z.infer<typeof JobSchema>;

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

export interface UploadTags {
  company: string;
  doc_type: DocType;
  period_end: string;
}
