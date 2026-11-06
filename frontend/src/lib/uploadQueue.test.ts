import { describe, expect, it } from "vitest";

import type { Job } from "@/api/types";

import { describeItem, isJobActive, queueReducer, type QueueItem } from "./uploadQueue";

const FILE = new File(["text"], "notes.txt", { lastModified: 1 });
const OTHER = new File(["other text"], "other.txt", { lastModified: 2 });

function added(): QueueItem[] {
  return queueReducer([], { type: "add", files: [FILE] });
}

function job(overrides: Partial<Job>): Job {
  return { status: "queued", progress: 0, error: null, chunks: null, ...overrides };
}

describe("queueReducer", () => {
  it("adds files as ready", () => {
    expect(added().map((item) => [item.file.name, item.state])).toEqual([["notes.txt", "ready"]]);
  });

  it("ignores a file that is already queued", () => {
    const items = queueReducer(added(), { type: "add", files: [FILE, OTHER] });

    expect(items.map((item) => item.file.name)).toEqual(["notes.txt", "other.txt"]);
  });

  it("follows a file through to its job", () => {
    const [{ id }] = added();
    const sending = queueReducer(added(), { type: "sending", id });
    const [submitted] = queueReducer(sending, { type: "submitted", id, jobId: "job" });

    expect(sending[0].state).toBe("sending");
    expect(submitted).toMatchObject({ state: "submitted", jobId: "job" });
  });

  it("records a rejection", () => {
    const [{ id }] = added();

    const [item] = queueReducer(added(), { type: "rejected", id, error: "Too big." });

    expect(item).toMatchObject({ state: "rejected", error: "Too big." });
  });

  it("removes only the given items", () => {
    const items = queueReducer(added(), { type: "add", files: [OTHER] });

    const left = queueReducer(items, { type: "remove", ids: [items[0].id] });

    expect(left.map((item) => item.file.name)).toEqual(["other.txt"]);
  });
});

describe("describeItem", () => {
  const submitted: QueueItem = { id: "a", file: FILE, state: "submitted", jobId: "job" };

  it("passes through the local states", () => {
    expect(describeItem({ ...submitted, state: "ready" }, undefined, false).kind).toBe("ready");
    expect(describeItem({ ...submitted, state: "sending" }, undefined, false).kind).toBe("sending");
  });

  it("shows a rejection as failed with the server's message", () => {
    const item: QueueItem = { ...submitted, state: "rejected", error: "No text." };

    expect(describeItem(item, undefined, false)).toEqual({ kind: "failed", error: "No text." });
  });

  it("treats a job not yet polled as queued", () => {
    expect(describeItem(submitted, undefined, false)).toEqual({
      kind: "working",
      label: "waiting to start",
      progress: 0,
    });
  });

  it("shows embedding progress", () => {
    expect(describeItem(submitted, job({ status: "embedding", progress: 60 }), false)).toEqual({
      kind: "working",
      label: "embedding passages",
      progress: 60,
    });
  });

  it("shows the finished chunk count", () => {
    expect(describeItem(submitted, job({ status: "indexed", chunks: 96 }), false)).toEqual({
      kind: "indexed",
      chunks: 96,
    });
  });

  it("shows a failed job's error", () => {
    expect(describeItem(submitted, job({ status: "failed", error: "Too short." }), false)).toEqual({
      kind: "failed",
      error: "Too short.",
    });
  });

  it("explains a job that disappeared", () => {
    const view = describeItem(submitted, undefined, true);

    expect(view.kind).toBe("failed");
  });
});

describe("isJobActive", () => {
  it("stops polling only on a final status", () => {
    expect(isJobActive(undefined)).toBe(true);
    expect(isJobActive(job({ status: "embedding" }))).toBe(true);
    expect(isJobActive(job({ status: "indexed" }))).toBe(false);
    expect(isJobActive(job({ status: "failed" }))).toBe(false);
  });
});
