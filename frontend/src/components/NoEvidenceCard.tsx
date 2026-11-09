import { CircleAlert } from "lucide-react";

import type { Passage } from "@/api/types";
import { Button } from "@/components/ui/button";
import { SectionLabel } from "@/components/SectionLabel";
import { passageLabel } from "@/lib/format";

interface NoEvidenceCardProps {
  retrieved: Passage[];
  onUpload: () => void;
  onRephrase: () => void;
}

export function NoEvidenceCard({ retrieved, onUpload, onRephrase }: NoEvidenceCardProps) {
  return (
    <article
      aria-labelledby="no-evidence-title"
      className="flex w-full max-w-[820px] flex-col gap-5 rounded-xl border bg-card p-7"
    >
      <div className="flex items-start gap-3.5 rounded-[10px] bg-warning-bg p-4 text-warning-fg">
        <CircleAlert aria-hidden="true" className="mt-0.5 size-[22px] flex-none" />
        <div className="flex flex-col gap-1.5">
          <h1 id="no-evidence-title" className="text-xl leading-[1.3] font-semibold">
            Not enough evidence in your documents
          </h1>
          <p className="text-[15px] leading-[1.6]">
            The retrieved passages do not answer this question, so no answer was written.
          </p>
        </div>
      </div>
      {retrieved.length > 0 && (
        <div className="flex flex-col gap-2.5">
          <SectionLabel>Closest passages found</SectionLabel>
          <ul className="flex flex-col gap-2">
            {retrieved.map((passage) => (
              <li
                key={passage.chunk_id}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg bg-muted px-3.5 py-3"
              >
                <span className="text-sm">{passageLabel(passage)}</span>
                <span className="font-mono text-xs text-muted-foreground">not cited</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-2.5">
        <Button onClick={onUpload} className="font-semibold">
          Upload a document
        </Button>
        <Button variant="outline" onClick={onRephrase}>
          Rephrase the question
        </Button>
      </div>
    </article>
  );
}
