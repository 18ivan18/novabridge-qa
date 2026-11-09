import { SectionLabel } from "@/components/SectionLabel";

// The first is eval question a23, answered from a 2026 table. The second has no year, so its answer
// covers both generations of filings. The last (u08) shows the no-evidence path.
const EXAMPLES = [
  { tag: "AAPL · 10-K 2026", question: "How much revenue did Apple earn from the iPhone in 2026?" },
  { tag: "AAPL · 2000 AND 2026", question: "What were Apple's total net sales?" },
  { tag: "NOT IN LIBRARY", question: "What was Tesla's revenue last year?" },
];

export function ExampleQuestions({ onPick }: { onPick: (question: string) => void }) {
  return (
    <section aria-labelledby="examples" className="flex flex-col gap-3">
      <SectionLabel id="examples">Try a question</SectionLabel>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
        {EXAMPLES.map(({ tag, question }) => (
          <button
            key={question}
            type="button"
            onClick={() => onPick(question)}
            className="flex min-h-11 flex-col gap-2 rounded-[10px] border bg-card p-4 text-left hover:border-input"
          >
            <span className="font-mono text-[11px] font-semibold text-muted-foreground">{tag}</span>
            <span className="text-[15px] leading-[1.45]">{question}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
