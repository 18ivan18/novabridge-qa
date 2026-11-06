import { useMutation, useQueries, useQueryClient, type Query } from "@tanstack/react-query";
import { useReducer } from "react";

import { ApiError, getJob, uploadDocument } from "@/api/client";
import type { Job, UploadTags } from "@/api/types";
import {
  describeItem,
  isJobActive,
  queueReducer,
  type ItemView,
  type QueueItem,
} from "@/lib/uploadQueue";

const POLL_INTERVAL_MS = 1000;

export interface QueueRow {
  item: QueueItem;
  view: ItemView;
}

/**
 * The upload queue. It lives above the dialog so that polling, and the library refresh it
 * triggers, carry on after the dialog closes.
 */
export function useUploadQueue() {
  const queryClient = useQueryClient();
  const [items, dispatch] = useReducer(queueReducer, []);
  const upload = useMutation({
    mutationFn: ({ file, tags }: { file: File; tags: UploadTags }) => uploadDocument(file, tags),
  });

  const jobIds = items.flatMap((item) => (item.jobId ? [item.jobId] : []));
  const jobQueries = useQueries({
    queries: jobIds.map((jobId) => ({
      queryKey: ["job", jobId],
      queryFn: async () => {
        const job = await getJob(jobId);
        if (job.status === "indexed") {
          await queryClient.invalidateQueries({ queryKey: ["documents"] });
        }
        return job;
      },
      retry: 1,
      refetchInterval: (query: Query<Job>) =>
        query.state.status !== "error" && isJobActive(query.state.data) ? POLL_INTERVAL_MS : false,
    })),
  });

  const rows: QueueRow[] = items.map((item) => {
    const query = item.jobId ? jobQueries[jobIds.indexOf(item.jobId)] : undefined;
    return { item, view: describeItem(item, query?.data, query?.isError ?? false) };
  });

  async function submit(tags: UploadTags) {
    // One at a time: the indexing runs in the background anyway, and files can be 20 MB each.
    for (const item of items.filter((candidate) => candidate.state === "ready")) {
      dispatch({ type: "sending", id: item.id });
      try {
        const { job_id: jobId } = await upload.mutateAsync({ file: item.file, tags });
        dispatch({ type: "submitted", id: item.id, jobId });
      } catch (error) {
        const message = error instanceof ApiError ? error.message : "Upload failed.";
        dispatch({ type: "rejected", id: item.id, error: message });
      }
    }
  }

  function removeWhere(matches: (row: QueueRow) => boolean) {
    dispatch({ type: "remove", ids: rows.filter(matches).map((row) => row.item.id) });
  }

  return {
    rows,
    submit,
    addFiles: (files: File[]) => dispatch({ type: "add", files }),
    remove: (id: string) => dispatch({ type: "remove", ids: [id] }),
    discardReady: () => removeWhere((row) => row.view.kind === "ready"),
    clearFinished: () =>
      removeWhere((row) => row.view.kind === "indexed" || row.view.kind === "failed"),
  };
}

export type UploadQueue = ReturnType<typeof useUploadQueue>;
