import { useState, type FormEvent } from "react";

import { NativeSelect } from "@/components/NativeSelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Scope } from "@/lib/scopes";

const MIN_LENGTH = 3;
const MAX_LENGTH = 1000;

interface AskFormProps {
  question: string;
  onQuestionChange: (question: string) => void;
  onSubmit: () => void;
  isPending: boolean;
}

function useValidatedSubmit({ question, onSubmit }: Pick<AskFormProps, "question" | "onSubmit">) {
  const [tooShort, setTooShort] = useState(false);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const invalid = question.trim().length < MIN_LENGTH;
    setTooShort(invalid);
    if (!invalid) onSubmit();
  }

  return { tooShort, handleSubmit };
}

function TooShort() {
  return (
    <p role="alert" className="text-sm text-error-fg">
      Please enter a question of at least {MIN_LENGTH} characters.
    </p>
  );
}

interface HomeAskFormProps extends AskFormProps {
  scopes: Scope[];
  scopeValue: string;
  onScopeChange: (value: string) => void;
}

/** The large form on the first screen. */
export function HomeAskForm(props: HomeAskFormProps) {
  const { question, onQuestionChange, isPending, scopes, scopeValue, onScopeChange } = props;
  const { tooShort, handleSubmit } = useValidatedSubmit(props);
  return (
    <form aria-label="Ask a question" onSubmit={handleSubmit} className="flex flex-col gap-2.5">
      <Label htmlFor="question" className="font-semibold">
        Question
      </Label>
      <Textarea
        id="question"
        rows={3}
        maxLength={MAX_LENGTH}
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder="e.g. How does Microsoft describe its competition?"
        className="rounded-[10px] border-input bg-card px-4 py-3.5 text-base leading-normal md:text-base"
      />
      {tooShort && <TooShort />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Label htmlFor="scope" className="font-normal text-muted-foreground">
            Search in
          </Label>
          <NativeSelect
            id="scope"
            value={scopeValue}
            onChange={(event) => onScopeChange(event.target.value)}
          >
            {scopes.map((scope) => (
              <option key={scope.value} value={scope.value}>
                {scope.label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <Button type="submit" disabled={isPending} className="px-6 text-[15px] font-semibold">
          Ask
        </Button>
      </div>
    </form>
  );
}

interface CompactAskFormProps extends AskFormProps {
  onNewQuestion: () => void;
}

/** The one-line form above an answer. */
export function CompactAskForm(props: CompactAskFormProps) {
  const { question, onQuestionChange, isPending, onNewQuestion } = props;
  const { tooShort, handleSubmit } = useValidatedSubmit(props);
  return (
    <form aria-label="Ask a question" onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2.5">
        <Label htmlFor="question" className="sr-only">
          Question
        </Label>
        <Input
          id="question"
          maxLength={MAX_LENGTH}
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          className="h-11 min-w-0 flex-[1_1_320px] rounded-lg border-input bg-card px-3.5 text-[15px] md:text-[15px]"
        />
        <Button type="submit" disabled={isPending} className="text-[15px] font-semibold">
          {isPending ? "Asking…" : "Ask"}
        </Button>
        <Button type="button" variant="link" onClick={onNewQuestion} className="h-11 px-2">
          New question
        </Button>
      </div>
      {tooShort && <TooShort />}
    </form>
  );
}
