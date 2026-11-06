import type { Job } from "@/api/types";

/** Where a file is on this side of the API. Once submitted, its job takes over. */
export interface QueueItem {
  id: string;
  file: File;
  state: "ready" | "sending" | "submitted" | "rejected";
  jobId?: string;
  error?: string;
}

export type QueueAction =
  | { type: "add"; files: File[] }
  | { type: "sending"; id: string }
  | { type: "submitted"; id: string; jobId: string }
  | { type: "rejected"; id: string; error: string }
  | { type: "remove"; ids: string[] };

function itemId(file: File): string {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

export function queueReducer(items: QueueItem[], action: QueueAction): QueueItem[] {
  switch (action.type) {
    case "add": {
      const known = new Set(items.map((item) => item.id));
      const added = action.files
        .map((file): QueueItem => ({ id: itemId(file), file, state: "ready" }))
        .filter((item) => !known.has(item.id));
      return [...items, ...added];
    }
    case "sending":
      return items.map((item) => (item.id === action.id ? { ...item, state: "sending" } : item));
    case "submitted":
      return items.map((item) =>
        item.id === action.id ? { ...item, state: "submitted", jobId: action.jobId } : item,
      );
    case "rejected":
      return items.map((item) =>
        item.id === action.id ? { ...item, state: "rejected", error: action.error } : item,
      );
    case "remove":
      return items.filter((item) => !action.ids.includes(item.id));
  }
}

export function isJobActive(job: Job | undefined): boolean {
  return job?.status !== "indexed" && job?.status !== "failed";
}

export type ItemView =
  | { kind: "ready" | "sending" }
  | { kind: "working"; label: string; progress: number }
  | { kind: "indexed"; chunks: number }
  | { kind: "failed"; error: string };

const WORKING_LABELS = {
  queued: "waiting to start",
  parsing: "reading the file",
  embedding: "embedding passages",
};

/** Combine a queue item with its job into the one state the row should show. */
export function describeItem(item: QueueItem, job: Job | undefined, pollFailed: boolean): ItemView {
  if (item.state === "ready" || item.state === "sending") return { kind: item.state };
  if (item.state === "rejected") return { kind: "failed", error: item.error ?? "Upload failed." };
  if (job?.status === "indexed") return { kind: "indexed", chunks: job.chunks ?? 0 };
  if (job?.status === "failed") {
    return { kind: "failed", error: job.error ?? "Indexing failed." };
  }
  // Jobs live in memory, so a server restart loses them. The file may still have been indexed.
  if (pollFailed) return { kind: "failed", error: "Lost track of this upload. Check the library." };
  const status = job?.status ?? "queued";
  return { kind: "working", label: WORKING_LABELS[status], progress: job?.progress ?? 0 };
}
