import { getAPIClient } from "@/core/api/api-client";
import { getBackendBaseURL } from "@/core/config";

import type {
  AgentVariantsResponse,
  GGLGraphResponse,
} from "./types";

export async function fetchAgentVariants(): Promise<AgentVariantsResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/agent-variants`);
  if (!response.ok) {
    throw new Error("Failed to fetch agent variants");
  }
  return response.json();
}

export async function fetchGGLGraph(
  threadId: string,
): Promise<GGLGraphResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/ggl/graph`,
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Failed to fetch GGL graph");
  }
  return response.json();
}

/** Update active node via LangGraph SDK; ggl_reducer merges into existing state.
 * No asNode - create_agent graph has opaque node names. Middleware reads from checkpoint as fallback.
 * @returns checkpoint for submit (pass to setPendingCheckpoint)
 */
export async function setActiveNode(
  threadId: string,
  nodeId: string,
): Promise<{ checkpoint_ns: string; checkpoint_id: string; checkpoint_map: Record<string, unknown> | null } | null> {
  const client = getAPIClient();
  const result = await client.threads.updateState(threadId, {
    values: { ggl: { active_node_id: nodeId } },
  });
  const cid = result?.configurable?.checkpoint_id;
  return typeof cid === "string"
    ? { checkpoint_ns: "", checkpoint_id: cid, checkpoint_map: {} }
    : null;
}
