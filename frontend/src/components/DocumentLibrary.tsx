import { Upload } from "lucide-react";

import type { LibraryDocument } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SectionLabel } from "@/components/SectionLabel";
import { documentBadge, documentDetails } from "@/lib/format";

interface DocumentLibraryProps {
  documents: LibraryDocument[] | undefined;
  isError: boolean;
  onUpload: () => void;
}

function Contents({ documents, isError }: Pick<DocumentLibraryProps, "documents" | "isError">) {
  if (isError) {
    return <p className="text-sm text-error-fg">The library could not be loaded.</p>;
  }
  if (!documents) {
    return (
      <div role="status" aria-label="Loading the library" className="flex flex-col gap-3">
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
      </div>
    );
  }
  if (documents.length === 0) {
    return (
      <p className="text-sm leading-normal text-muted-foreground">
        No documents yet. Upload one to start asking questions.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-0.5">
      {documents.map((document) => (
        <li key={document.doc_id} className="flex items-start gap-2.5 rounded-lg px-2 py-2.5">
          <span className="min-w-10 flex-none rounded bg-secondary px-1.5 py-0.5 text-center font-mono text-[11px] font-semibold text-secondary-foreground">
            {documentBadge(document)}
          </span>
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="text-sm font-medium wrap-anywhere">{document.title}</span>
            <span className="text-xs text-muted-foreground">{documentDetails(document)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function DocumentLibrary({ documents, isError, onUpload }: DocumentLibraryProps) {
  return (
    <aside
      aria-label="Document library"
      className="flex flex-[1_1_260px] flex-col gap-4 border-r bg-card p-5"
    >
      <SectionLabel>Document library</SectionLabel>
      <Button
        variant="outline"
        onClick={onUpload}
        className="border-primary font-semibold text-primary"
      >
        <Upload aria-hidden="true" />
        Upload document
      </Button>
      <Contents documents={documents} isError={isError} />
    </aside>
  );
}
