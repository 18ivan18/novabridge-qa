import { useEffect, useRef, useState } from "react";

import type { AskResponse } from "@/api/types";
import { AnswerCard } from "@/components/AnswerCard";
import { SourceCard } from "@/components/SourceCard";
import { passageLabel, plural, retrievalLine } from "@/lib/format";

const HIGHLIGHT_MS = 2000;

interface AnswerViewProps {
  question: string;
  scopeLabel: string;
  response: AskResponse;
}

function useSourceHighlight() {
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  function select(id: number) {
    const card = document.getElementById(`src-${id}`);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    card?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
    card?.focus({ preventScroll: true });
    setHighlighted(id);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setHighlighted(null), HIGHLIGHT_MS);
  }

  return { highlighted, select };
}

export function AnswerView({ question, scopeLabel, response }: AnswerViewProps) {
  const { sources, retrieved } = response;
  const [showDetails, setShowDetails] = useState(false);
  const { highlighted, select } = useSourceHighlight();
  const cited = new Set(sources.map((source) => source.chunk_id));
  const uncited = retrieved.filter((passage) => !cited.has(passage.chunk_id));

  return (
    <div className="flex flex-wrap items-start gap-6">
      <AnswerCard
        question={question}
        scopeLabel={scopeLabel}
        response={response}
        showDetails={showDetails}
        onToggleDetails={() => setShowDetails(!showDetails)}
        onSelectSource={select}
      />
      <aside
        aria-labelledby="sources-title"
        className="flex min-w-0 flex-[2_1_320px] flex-col gap-3"
      >
        <div className="flex items-baseline justify-between gap-2">
          <h2
            id="sources-title"
            className="text-xs font-semibold tracking-[0.06em] text-muted-foreground uppercase"
          >
            Sources
          </h2>
          <span className="text-xs text-muted-foreground">
            {sources.length} cited of {retrieved.length} retrieved
          </span>
        </div>
        <ol className="flex flex-col gap-3">
          {sources.map((source) => (
            <SourceCard
              key={source.id}
              source={source}
              highlighted={highlighted === source.id}
              showDetails={showDetails}
            />
          ))}
        </ol>
        {uncited.length > 0 && (
          <details className="rounded-[10px] border bg-card px-4 py-3 text-sm">
            <summary className="min-h-6 cursor-pointer font-medium">
              {plural(uncited.length, "more passage")} retrieved but not cited
            </summary>
            <ul className="mt-2.5 flex flex-col gap-1 text-[13px] leading-normal text-muted-foreground">
              {uncited.map((passage) => (
                <li key={passage.chunk_id}>
                  {passageLabel(passage)}
                  {showDetails && (
                    <span className="block font-mono text-xs">{retrievalLine(passage)}</span>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
      </aside>
    </div>
  );
}
