import { useState } from "react";

import type { Source } from "@/api/types";
import { Button } from "@/components/ui/button";
import { retrievalLine, sourceLocation, sourceTitle, unwrapExcerpt } from "@/lib/format";

interface SourceCardProps {
  source: Source;
  highlighted: boolean;
  showDetails: boolean;
}

export function SourceCard({ source, highlighted, showDetails }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li
      id={`src-${source.id}`}
      // -1 lets a citation chip move keyboard focus here without adding a tab stop.
      tabIndex={-1}
      data-highlighted={highlighted}
      className="flex flex-col gap-2.5 rounded-[10px] border bg-card p-4 transition-shadow outline-none data-[highlighted=true]:border-primary data-[highlighted=true]:ring-2 data-[highlighted=true]:ring-primary"
    >
      <div className="flex items-start gap-2.5">
        <span className="inline-flex h-6 min-w-6 flex-none items-center justify-center rounded-md bg-chip font-mono text-xs font-semibold text-primary">
          {source.id}
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-sm font-semibold wrap-anywhere">{sourceTitle(source)}</span>
          <span className="text-[13px] text-muted-foreground">{sourceLocation(source)}</span>
        </div>
      </div>
      <p
        className={`rounded-lg bg-muted p-3 text-sm leading-[1.55] whitespace-pre-line text-secondary-foreground ${expanded ? "" : "line-clamp-4"}`}
      >
        {unwrapExcerpt(source.excerpt)}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {showDetails && (
          <span className="font-mono text-xs text-muted-foreground">{retrievalLine(source)}</span>
        )}
        <Button
          variant="link"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
          className="ml-auto h-11 px-0 text-[13px]"
        >
          {expanded ? "Show less" : "Show full passage"}
        </Button>
      </div>
    </li>
  );
}
