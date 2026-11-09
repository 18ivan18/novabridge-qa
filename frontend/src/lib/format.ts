import type { ClientConfig, DocType, LibraryDocument, Passage } from "@/api/types";

const DOC_TYPE_LABELS: Record<DocType, string> = {
  "10-K": "Form 10-K",
  "10-Q": "Form 10-Q",
  "8-K": "Form 8-K",
  earnings_call: "Earnings call",
  news: "News article",
  other: "Other",
};

export const DOC_TYPES = Object.keys(DOC_TYPE_LABELS) as DocType[];

export function docTypeLabel(docType: DocType): string {
  return DOC_TYPE_LABELS[docType];
}

/** Reads the year from the text: parsing the date could shift it across a time zone. */
function fiscalYear(periodEnd: string | null): string | null {
  return periodEnd ? `FY${periodEnd.slice(0, 4)}` : null;
}

function join(parts: (string | null)[], separator = " · "): string {
  return parts.filter(Boolean).join(separator);
}

/** The bold line of a source card, such as "AAPL · Form 10-K · FY2000". */
export function sourceTitle(passage: Passage): string {
  if (!passage.ticker) return passage.title;
  return join([passage.ticker, docTypeLabel(passage.doc_type), fiscalYear(passage.period_end)]);
}

export function sourceLocation(passage: Passage): string {
  return join([passage.section, passage.page === null ? null : `Page ${passage.page}`]);
}

/** One line for lists of passages, such as "AAPL 10-K · Item 7". */
export function passageLabel(passage: Passage): string {
  const name = passage.ticker ? `${passage.ticker} ${passage.doc_type}` : passage.title;
  return join([name, passage.section]);
}

const isTableRow = (line: string) => /\S {2,}\S/.test(line);

/** Rejoin the hard-wrapped lines of filings so text can reflow, but keep table rows apart. */
export function unwrapExcerpt(text: string): string {
  const lines = text.split("\n");
  return lines
    .map((line, index) => {
      const next = lines[index + 1];
      if (next === undefined) return line;
      const flowing = line && next && !isTableRow(line) && !isTableRow(next);
      return line + (flowing ? " " : "\n");
    })
    .join("");
}

export function retrievalLine(passage: Passage): string {
  const { dense_rank, sparse_rank, rrf_score, rerank_rank } = passage.retrieval;
  const rank = (value: number | null) => (value === null ? "–" : `#${value}`);
  const fused = `bm25 ${rank(sparse_rank)} · dense ${rank(dense_rank)} · rrf ${rrf_score.toFixed(4)}`;
  return rerank_rank === null ? fused : `rerank #${rerank_rank} · ${fused}`;
}

/** The badge in the library: the ticker, or the file type for uploads. */
export function documentBadge(document: LibraryDocument): string {
  if (document.ticker) return document.ticker;
  return document.filename.split(".").pop()?.toUpperCase() ?? "DOC";
}

function uploadedLabel(ingestedAt: string, now: Date): string {
  const date = new Date(ingestedAt);
  if (date.toDateString() === now.toDateString()) return "Uploaded today";
  const day = date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return `Uploaded ${day}`;
}

export function documentDetails(document: LibraryDocument, now = new Date()): string {
  const when =
    document.source === "upload"
      ? uploadedLabel(document.ingested_at, now)
      : fiscalYear(document.period_end);
  return join([when, plural(document.chunks, "chunk")]);
}

export function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

const FILE_TYPE_NAMES: Record<string, string> = {
  ".htm": "HTML",
  ".html": "HTML",
  ".md": "Markdown",
  ".pdf": "PDF",
  ".txt": "TXT",
};

/** The upload hint, such as "HTML, Markdown or TXT · up to 20 MB each", from GET /api/config. */
export function uploadLimits(config: ClientConfig): string {
  const names = [
    ...new Set(
      config.upload_types.map((suffix) => FILE_TYPE_NAMES[suffix] ?? suffix.slice(1).toUpperCase()),
    ),
  ];
  const types = names.length > 1 ? `${names.slice(0, -1).join(", ")} or ${names.at(-1)}` : names[0];
  return join([types ?? null, `up to ${config.max_upload_mb} MB each`]);
}
