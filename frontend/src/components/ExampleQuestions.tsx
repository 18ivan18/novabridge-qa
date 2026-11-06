// Taken from eval/questions.jsonl, so they match the indexed filings: the first two have answers
// in the library and the last shows the no-evidence path.
const EXAMPLES = [
  {
    tag: "AAPL · 10-K",
    question: "What happens to Apple if a key component only available from one vendor is delayed?",
  },
  { tag: "NVDA · 10-K", question: "Who are NVIDIA's largest customers?" },
  { tag: "NOT IN LIBRARY", question: "What was Tesla's revenue last year?" },
];

export function ExampleQuestions({ onPick }: { onPick: (question: string) => void }) {
  return (
    <section aria-labelledby="examples" className="flex flex-col gap-3">
      <h2
        id="examples"
        className="text-xs font-semibold tracking-[0.06em] text-muted-foreground uppercase"
      >
        Try a question
      </h2>
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
