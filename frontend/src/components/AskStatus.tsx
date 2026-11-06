import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function AnswerSkeleton() {
  return (
    <div
      role="status"
      aria-label="Searching the documents and writing an answer"
      className="flex max-w-[820px] flex-col gap-4 rounded-xl border bg-card p-7"
    >
      <Skeleton className="h-7 w-2/3" />
      <Skeleton className="h-4" />
      <Skeleton className="h-4" />
      <Skeleton className="h-4 w-4/5" />
    </div>
  );
}

export function AskError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="flex max-w-[820px] flex-col items-start gap-3 rounded-xl border border-error-border bg-error-bg p-6 text-error-fg"
    >
      <h1 className="text-lg font-semibold">The answer could not be generated</h1>
      <p className="text-[15px] leading-[1.6]">{message}</p>
      <Button variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
