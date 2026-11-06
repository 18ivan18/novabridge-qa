import type {
  AskRequest,
  AskResponse,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, NETWORK_ERROR);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "The server sent a response that could not be read.");
  }
}

export function getHealth(): Promise<Health> {
  return request("/health");
}

export function getDocuments(): Promise<LibraryDocument[]> {
  return request("/documents");
}

export function askQuestion(body: AskRequest): Promise<AskResponse> {
  return request("/ask", {
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
  return request("/documents", { method: "POST", body: form });
}

export function getJob(jobId: string): Promise<Job> {
  return request(`/jobs/${encodeURIComponent(jobId)}`);
}
