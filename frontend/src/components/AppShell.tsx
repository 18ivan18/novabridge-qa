import type { ReactNode } from "react";

interface AppShellProps {
  llmProvider?: string;
  onHome: () => void;
  sidebar: ReactNode;
  children: ReactNode;
}

const PILL = "rounded-md border border-border px-2 py-1";

export function AppShell({ llmProvider, onHome, sidebar, children }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b bg-card px-6 py-3.5">
        <button type="button" onClick={onHome} className="flex items-center gap-3">
          <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
            <rect x="1" y="1" width="26" height="26" rx="6" fill="var(--primary)" />
            <path
              d="M8 19 L12.5 13 L16 16.5 L20 9"
              stroke="#FFFFFF"
              strokeWidth="2"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="flex items-baseline gap-2">
            <span className="text-base font-bold">NovaBridge</span>
            <span className="text-sm text-muted-foreground">Analyst Q&amp;A</span>
          </span>
        </button>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {llmProvider && <span className={`${PILL} font-mono`}>LLM · {llmProvider}</span>}
          <span className={PILL}>Internal prototype</span>
        </div>
      </header>
      <div className="flex flex-auto flex-wrap items-stretch">
        {sidebar}
        <main className="flex min-w-0 flex-[999_1_560px] flex-col gap-6 px-8 pt-7 pb-10">
          {children}
          <p className="mt-auto text-xs leading-normal text-muted-foreground">
            Answers come only from indexed documents and may be incomplete. Always check the cited
            passages. Not investment advice.
          </p>
        </main>
      </div>
    </div>
  );
}
