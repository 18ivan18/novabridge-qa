import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { makePassage, makeResponse, makeSource } from "@/test/fixtures";

import { AnswerCard } from "./AnswerCard";

function renderCard(overrides: Partial<Parameters<typeof AnswerCard>[0]> = {}) {
  const onSelectSource = vi.fn();
  const onToggleDetails = vi.fn();
  render(
    <AnswerCard
      question="Who sells anvils?"
      scopeLabel="All documents"
      response={makeResponse()}
      showDetails={false}
      onToggleDetails={onToggleDetails}
      onSelectSource={onSelectSource}
      {...overrides}
    />,
  );
  return { onSelectSource, onToggleDetails };
}

describe("AnswerCard", () => {
  it("renders each citation as a labelled link to its source", () => {
    renderCard();

    const chip = screen.getByRole("link", { name: "Source 2" });
    expect(chip.getAttribute("href")).toBe("#src-2");
    expect(chip.textContent).toBe("2");
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });

  it("keeps the text around the citations and removes the brackets", () => {
    renderCard();

    const text = screen.getByRole("article").textContent;
    expect(text).toContain("ACME sells anvils 1. They are heavy 2.");
  });

  it("tells the parent which source was clicked", () => {
    const { onSelectSource } = renderCard();

    fireEvent.click(screen.getByRole("link", { name: "Source 1" }));

    expect(onSelectSource).toHaveBeenCalledWith(1);
  });

  it("leaves a citation with no source as plain text", () => {
    const response = makeResponse({ answer: "Anvils [1] and [7].", sources: [makeSource(1)] });
    renderCard({ response });

    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByRole("article").textContent).toContain("[7]");
  });

  it("renders paragraphs separately", () => {
    renderCard({ response: makeResponse({ answer: "First [1].\n\nSecond [2]." }) });

    const article = screen.getByRole("article");
    expect(within(article).getByText(/^First/).tagName).toBe("P");
    expect(within(article).getByText(/^Second/).tagName).toBe("P");
  });

  it("summarizes the retrieval", () => {
    renderCard();

    expect(
      screen.getByText(
        "hybrid retrieval + re-ranking · 3 passages · 2 cited · scope: all documents",
      ),
    ).toBeTruthy();
    expect(screen.getByText("All 2 citations point to retrieved passages")).toBeTruthy();
  });

  it("leaves re-ranking out of the summary when it did not run", () => {
    const unranked = (number: number) => {
      const passage = makePassage(number);
      return { ...passage, retrieval: { ...passage.retrieval, rerank_rank: null } };
    };
    renderCard({ response: makeResponse({ retrieved: [unranked(1), unranked(2)] }) });

    expect(screen.getByText(/^hybrid retrieval · 2 passages/)).toBeTruthy();
  });

  it("shows timings only with the details open", () => {
    renderCard({ showDetails: true });

    expect(screen.getByText("retrieval 12 ms · generation 340 ms")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Hide retrieval details" })).toBeTruthy();
  });

  it("copies the answer", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    renderCard();

    fireEvent.click(screen.getByRole("button", { name: "Copy answer" }));

    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
    expect(writeText).toHaveBeenCalledWith("ACME sells anvils [1]. They are heavy [2].");
  });

  it("says so when the browser refuses the clipboard", async () => {
    const writeText = vi.fn().mockRejectedValue(new DOMException("Denied", "NotAllowedError"));
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    renderCard();

    fireEvent.click(screen.getByRole("button", { name: "Copy answer" }));

    expect(await screen.findByRole("button", { name: "Copy failed" })).toBeTruthy();
  });
});
