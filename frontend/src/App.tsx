import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, askQuestion, getDocuments, getHealth } from "@/api/client";
import { AnswerView } from "@/components/AnswerView";
import { AppShell } from "@/components/AppShell";
import { CompactAskForm, HomeAskForm } from "@/components/AskForm";
import { AnswerSkeleton, AskError } from "@/components/AskStatus";
import { DocumentLibrary } from "@/components/DocumentLibrary";
import { ExampleQuestions } from "@/components/ExampleQuestions";
import { NoEvidenceCard } from "@/components/NoEvidenceCard";
import { UploadDialog } from "@/components/UploadDialog";
import { useUploadQueue } from "@/hooks/useUploadQueue";
import { ALL_DOCUMENTS, buildScopes, type Scope } from "@/lib/scopes";

/** What was asked, kept apart from the form, whose text can change while an answer is on screen. */
interface Asked {
  question: string;
  scope: Scope;
}

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth });
  const documents = useQuery({ queryKey: ["documents"], queryFn: getDocuments });
  const ask = useMutation({ mutationFn: askQuestion });
  const queue = useUploadQueue();

  const [question, setQuestion] = useState("");
  const [scopeValue, setScopeValue] = useState(ALL_DOCUMENTS.value);
  const [asked, setAsked] = useState<Asked | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  const scopes = buildScopes(documents.data ?? []);
  const scope = scopes.find((candidate) => candidate.value === scopeValue) ?? ALL_DOCUMENTS;

  function submit(text: string, chosen: Scope) {
    const trimmed = text.trim();
    setQuestion(trimmed);
    setAsked({ question: trimmed, scope: chosen });
    ask.mutate({ question: trimmed, filters: chosen.filters });
  }

  function backToForm(text: string) {
    ask.reset();
    setAsked(null);
    setQuestion(text);
  }

  const errorMessage =
    ask.error instanceof ApiError ? ask.error.message : "Something went wrong. Please try again.";

  return (
    <AppShell
      llmProvider={health.data?.llm_provider}
      onHome={() => backToForm("")}
      sidebar={
        <DocumentLibrary
          documents={documents.data}
          isError={documents.isError}
          onUpload={() => setUploadOpen(true)}
        />
      }
    >
      {asked === null ? (
        <div className="mx-auto flex w-full max-w-[760px] flex-col gap-10 pt-7">
          <div className="flex flex-col gap-2">
            <h1 className="text-[30px] leading-[1.2] font-semibold">
              Ask about the indexed filings
            </h1>
            <p className="text-base leading-[1.55] text-muted-foreground">
              Answers are written only from the documents in your library, with numbered citations
              you can open and check.
            </p>
          </div>
          <HomeAskForm
            question={question}
            onQuestionChange={setQuestion}
            onSubmit={() => submit(question, scope)}
            isPending={ask.isPending}
            scopes={scopes}
            scopeValue={scope.value}
            onScopeChange={setScopeValue}
          />
          {(documents.data?.length ?? 0) > 0 && (
            <ExampleQuestions onPick={(example) => submit(example, ALL_DOCUMENTS)} />
          )}
        </div>
      ) : (
        <>
          <CompactAskForm
            question={question}
            onQuestionChange={setQuestion}
            onSubmit={() => submit(question, asked.scope)}
            isPending={ask.isPending}
            onNewQuestion={() => backToForm("")}
          />
          {ask.isPending && <AnswerSkeleton />}
          {ask.isError && (
            <AskError message={errorMessage} onRetry={() => submit(asked.question, asked.scope)} />
          )}
          {ask.data?.insufficient_evidence === true && (
            <NoEvidenceCard
              retrieved={ask.data.retrieved}
              onUpload={() => setUploadOpen(true)}
              onRephrase={() => backToForm(asked.question)}
            />
          )}
          {ask.data?.insufficient_evidence === false && (
            <AnswerView
              // A new answer starts with its details hidden and nothing highlighted.
              key={ask.submittedAt}
              question={asked.question}
              scopeLabel={asked.scope.label}
              response={ask.data}
            />
          )}
        </>
      )}
      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} queue={queue} />
    </AppShell>
  );
}
