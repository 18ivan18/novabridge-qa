import { describe, expect, it } from "vitest";

import { makePassage } from "@/test/fixtures";

import { retrievalLine } from "./format";

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
