import { describe, expect, it, vi } from "vitest";

import { ApiError, askQuestion, getDocuments, uploadDocument } from "./client";

function stubFetch(response: Response | Error) {
  const mock = vi.fn(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal("fetch", mock);
  return mock;
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

async function failure(call: () => Promise<unknown>): Promise<ApiError> {
  const error: unknown = await call().catch((caught: unknown) => caught);
  expect(error).toBeInstanceOf(ApiError);
  return error as ApiError;
}

describe("api client", () => {
  it("returns the parsed body", async () => {
    stubFetch(json([{ doc_id: "doc" }]));

    expect(await getDocuments()).toEqual([{ doc_id: "doc" }]);
  });

  it("posts questions as JSON", async () => {
    const mock = stubFetch(json({}));

    await askQuestion({ question: "Who sells anvils?" });

    const [path, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/ask");
    expect(init.body).toBe('{"question":"Who sells anvils?"}');
  });

  it("surfaces the friendly detail from the API", async () => {
    stubFetch(json({ detail: "The LLM provider rejected the API key." }, 502));

    const error = await failure(getDocuments);

    expect(error.status).toBe(502);
    expect(error.message).toBe("The LLM provider rejected the API key.");
  });

  it("hides FastAPI's validation list", async () => {
    stubFetch(json({ detail: [{ loc: ["body"], msg: "too short", type: "string" }] }, 422));

    expect((await failure(getDocuments)).message).toBe(
      "Please check what you entered and try again.",
    );
  });

  it("copes with an HTML error page from a proxy", async () => {
    stubFetch(new Response("<html>Bad gateway</html>", { status: 502 }));

    expect((await failure(getDocuments)).message).toContain("status 502");
  });

  it("reports a network failure without the raw error", async () => {
    stubFetch(new TypeError("Failed to fetch"));

    const error = await failure(getDocuments);

    expect(error.status).toBe(0);
    expect(error.message).toBe("Could not reach the server. Check that the API is running.");
  });

  it("reports a success body that is not JSON", async () => {
    stubFetch(new Response("<html></html>", { status: 200 }));

    expect((await failure(getDocuments)).message).toContain("could not be read");
  });

  it("leaves an empty period out of an upload", async () => {
    const mock = stubFetch(json({ job_id: "j", doc_id: "d" }, 202));
    const file = new File(["text"], "notes.txt");

    await uploadDocument(file, { company: "ACME", doc_type: "other", period_end: "" });

    const [, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    const form = init.body as FormData;
    expect(form.get("company")).toBe("ACME");
    expect(form.has("period_end")).toBe(false);
  });
});
