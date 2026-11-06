import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { QueueRow } from "@/hooks/useUploadQueue";
import { fileSize, plural } from "@/lib/format";

interface UploadQueueItemProps {
  row: QueueRow;
  onRemove: (id: string) => void;
}

const PILL = "rounded-full px-2.5 py-1 text-xs font-semibold";

function subtitle({ item, view }: QueueRow): string {
  const size = fileSize(item.file.size);
  switch (view.kind) {
    case "ready":
      return `${size} · ready to upload`;
    case "sending":
      return `${size} · sending`;
    case "working":
      return `${size} · ${view.label}`;
    case "indexed":
      return `${size} · ${plural(view.chunks, "passage")}`;
    case "failed":
      return view.error;
  }
}

export function UploadQueueItem({ row, onRemove }: UploadQueueItemProps) {
  const { item, view } = row;
  const failed = view.kind === "failed";
  return (
    <li
      className={`flex flex-col gap-2.5 rounded-[10px] border px-3.5 py-3 ${failed ? "border-error-border bg-error-bg" : ""}`}
    >
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex min-w-0 flex-[1_1_220px] flex-col gap-0.5">
          <span className="text-sm font-medium wrap-anywhere">{item.file.name}</span>
          <span className={`text-xs leading-[1.45] ${failed ? "text-error-fg" : "text-muted-foreground"}`}>
            {subtitle(row)}
          </span>
        </div>
        {view.kind === "working" && (
          <span className={`${PILL} bg-chip text-primary`}>{view.progress}%</span>
        )}
        {view.kind === "indexed" && (
          <span className={`${PILL} inline-flex items-center gap-1.5 bg-success-bg text-success-fg`}>
            <Check aria-hidden="true" className="size-3" strokeWidth={3} />
            Indexed
          </span>
        )}
        {(failed || view.kind === "ready") && (
          <Button variant="outline" onClick={() => onRemove(item.id)} className="px-3.5 text-[13px]">
            Remove
          </Button>
        )}
      </div>
      {view.kind === "working" && (
        <Progress
          value={view.progress}
          aria-label={`Progress for ${item.file.name}`}
          className="h-1.5 bg-[#ECEAE3]"
        />
      )}
    </li>
  );
}
