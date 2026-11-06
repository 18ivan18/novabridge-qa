import type { AskFilters, LibraryDocument } from "@/api/types";

export interface Scope {
  value: string;
  label: string;
  filters?: AskFilters;
}

export const ALL_DOCUMENTS: Scope = { value: "all", label: "All documents" };

/** Build the "Search in" options from what is really in the library. */
export function buildScopes(documents: LibraryDocument[]): Scope[] {
  const companies = new Map<string, string>();
  for (const document of documents) {
    if (document.ticker) companies.set(document.ticker, document.company);
  }
  const scopes: Scope[] = [ALL_DOCUMENTS];
  for (const [ticker, company] of companies) {
    scopes.push({ value: ticker, label: company, filters: { tickers: [ticker] } });
  }
  if (documents.some((document) => document.source === "upload")) {
    scopes.push({ value: "uploads", label: "My uploads", filters: { sources: ["upload"] } });
  }
  return scopes;
}
