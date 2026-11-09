import { Check } from "lucide-react";
import { useMemo, useState } from "react";

import type { AskResponse } from "@/api/types";
import { CitationChip } from "@/components/CitationChip";
import { Button } from "@/components/ui/button";
import { parseAnswer } from "@/lib/citations";
import { plural } from "@/lib/format";

interface AnswerCardProps {
  question: string;
  scopeLabel: string;
  response: AskResponse;
  showDetails: boolean;
  onToggleDetails: () => void;
  onSelectSource: (id: number) => void;
}

export function AnswerCard({
  question,
  scopeLabel,
  response,
  showDetails,
  onToggleDetails,
  onSelectSource,
}: AnswerCardProps) {
  const { answer, sources, retrieved, timings_ms: timings } = response;
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const paragraphs = useMemo(
    () => parseAnswer(answer, new Set(sources.map((source) => source.id))),
    [answer, sources],
  );
  // Re-ranking can be switched off on the server; the passages say whether it ran.
  const method = retrieved.some((passage) => passage.retrieval.rerank_rank !== null)
    ? "hybrid retrieval + re-ranking"
    : "hybrid retrieval";

  async function copy() {
    try {
      // Rejected outside a secure context, or when the browser denies clipboard access.
      await navigator.clipboard.writeText(answer);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  return (
    <article
      aria-labelledby="answer-title"
      className="flex min-w-0 flex-[3_1_460px] flex-col gap-[18px] rounded-xl border bg-card p-7"
    >
      <div className="flex flex-col gap-1.5">
        <h1 id="answer-title" className="text-[22px] leading-[1.3] font-semibold">
          {question}
        </h1>
        <p className="font-mono text-xs text-muted-foreground">
          {method} · {plural(retrieved.length, "passage")} · {sources.length} cited · scope:{" "}
          {scopeLabel.toLowerCase()}
        </p>
      </div>
      <div className="flex flex-col gap-3.5 text-base leading-[1.7]">
        {paragraphs.map((parts, paragraphIndex) => (
          <p key={paragraphIndex}>
            {parts.map((part, partIndex) =>
              part.kind === "text" ? (
                part.text
              ) : (
                <CitationChip key={partIndex} id={part.id} onSelect={onSelectSource} />
              ),
            )}
          </p>
        ))}
      </div>
      <div className="flex items-center gap-2 rounded-lg bg-success-bg px-3 py-2.5 text-[13px] font-medium text-success-fg">
        <Check aria-hidden="true" className="size-4" />
        {sources.length === 1
          ? "The citation points to a retrieved passage"
          : `All ${sources.length} citations point to retrieved passages`}
      </div>
      {showDetails && (
        <p className="font-mono text-xs text-muted-foreground">
          retrieval {timings.retrieval} ms · generation {timings.generation} ms
        </p>
      )}
      <div className="flex flex-wrap gap-2.5">
        <Button variant="outline" onClick={() => void copy()}>
          {{ idle: "Copy answer", copied: "Copied", failed: "Copy failed" }[copyState]}
        </Button>
        <Button variant="outline" aria-pressed={showDetails} onClick={onToggleDetails}>
          {showDetails ? "Hide retrieval details" : "Show retrieval details"}
        </Button>
      </div>
    </article>
  );
}
