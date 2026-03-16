import { getBackendBaseURL } from "@/core/config";

export interface ThreadInfoResponse {
  thread_id: string;
  agent_variant: string | null;
}

export async function fetchThreadInfo(threadId: string): Promise<ThreadInfoResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/info`,
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Failed to fetch thread info");
  }
  return response.json();
}

export async function deleteThread(threadId: string): Promise<void> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Failed to delete thread");
  }
}
