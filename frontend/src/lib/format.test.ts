import { describe, expect, it } from "vitest";

import { makePassage } from "@/test/fixtures";

import { retrievalLine, uploadLimits } from "./format";

describe("retrievalLine", () => {
  it("leads with the re-ranker rank, which sets the order", () => {
    expect(retrievalLine(makePassage(2))).toBe("rerank #2 · bm25 – · dense #2 · rrf 0.0323");
  });

  it("leaves the re-ranker out when it is off", () => {
    const p = makePassage(2);
    const off = { ...p, retrieval: { ...p.retrieval, rerank_rank: null } };

    expect(retrievalLine(off)).toBe("bm25 – · dense #2 · rrf 0.0323");
  });
});

describe("uploadLimits", () => {
  it("names each format once and states the size limit", () => {
    const config = { upload_types: [".htm", ".html", ".md", ".txt"], max_upload_mb: 20 };

    expect(uploadLimits(config)).toBe("HTML, Markdown or TXT · up to 20 MB each");
  });

  it("falls back to the suffix for a format it has no name for", () => {
    expect(uploadLimits({ upload_types: [".csv"], max_upload_mb: 5 })).toBe(
      "CSV · up to 5 MB each",
    );
  });
});
