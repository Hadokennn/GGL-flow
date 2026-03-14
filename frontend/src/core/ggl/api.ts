import { getBackendBaseURL } from "@/core/config";

import type {
  ActiveNodeResponse,
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

export async function setActiveNode(
  threadId: string,
  nodeId: string,
): Promise<ActiveNodeResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/ggl/active-node`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ node_id: nodeId }),
    },
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Failed to set active node");
  }
  return response.json();
}
