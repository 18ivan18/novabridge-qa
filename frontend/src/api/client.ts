import { z } from "zod";

import {
  AskResponseSchema,
  ClientConfigSchema,
  HealthSchema,
  JobSchema,
  LibraryDocumentSchema,
  UploadResponseSchema,
} from "./schemas";
import type {
  AskRequest,
  AskResponse,
  ClientConfig,
  Health,
  Job,
  LibraryDocument,
  UploadResponse,
  UploadTags,
} from "./types";

const NETWORK_ERROR = "Could not reach the server. Check that the API is running.";
const INVALID_INPUT = "Please check what you entered and try again.";

/** A failed request. `message` is always safe and useful to show to the user. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function errorMessage(response: Response): Promise<string> {
  const fallback = `The server could not handle the request (status ${response.status}).`;
  try {
    const body: unknown = await response.json();
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    // FastAPI's own validation errors are a list written for developers.
    if (Array.isArray(detail)) return INVALID_INPUT;
    return fallback;
  } catch {
    // A proxy in front of the API can answer with an HTML error page.
    return fallback;
  }
}

/**
 * Check a response body against its schema. A mismatch is logged rather than thrown: the body is
 * still used as it is, so a harmless change on the server, such as a new field, warns a developer
 * in the console without breaking the page.
 */
function checked<S extends z.ZodType>(path: string, schema: S, body: unknown): z.infer<S> {
  const result = schema.safeParse(body);
  if (result.success) return result.data;
  console.warn(`Unexpected response from /api${path}`, result.error.issues);
  return body as z.infer<S>;
}

async function request<S extends z.ZodType>(
  path: string,
  schema: S,
  init?: RequestInit,
): Promise<z.infer<S>> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, NETWORK_ERROR);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(response.status, "The server sent a response that could not be read.");
  }
  return checked(path, schema, body);
}

export function getHealth(): Promise<Health> {
  return request("/health", HealthSchema);
}

export function getConfig(): Promise<ClientConfig> {
  return request("/config", ClientConfigSchema);
}

export function getDocuments(): Promise<LibraryDocument[]> {
  return request("/documents", z.array(LibraryDocumentSchema));
}

export function askQuestion(body: AskRequest): Promise<AskResponse> {
  return request("/ask", AskResponseSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function uploadDocument(file: File, tags: UploadTags): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("company", tags.company);
  form.append("doc_type", tags.doc_type);
  // The API parses this field as a date, so an empty string would be rejected.
  if (tags.period_end) form.append("period_end", tags.period_end);
  return request("/documents", UploadResponseSchema, { method: "POST", body: form });
}

export function getJob(jobId: string): Promise<Job> {
  return request(`/jobs/${encodeURIComponent(jobId)}`, JobSchema);
}
