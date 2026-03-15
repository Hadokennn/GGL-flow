import { getBackendBaseURL } from "@/core/config";

import type {
  ActiveNodeResponse,
  AgentVariantsResponse,
  GGLGraphResponse,
  InitGraphRequest,
  InitGraphResponse,
  KnowledgeCardResponse,
  SurveyAnswersRequest,
  SurveyAnswersResponse,
  SurveyRequest,
  SurveyResponse,
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

export async function fetchKnowledgeCard(
  threadId: string,
  nodeId: string,
): Promise<KnowledgeCardResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/ggl/knowledge-card/${nodeId}`,
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Failed to fetch knowledge card");
  }
  return response.json();
}

export async function initGGLGraph(
  threadId: string,
  payload: InitGraphRequest,
): Promise<InitGraphResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/ggl/init`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : error.detail?.message ?? "Failed to initialize GGL graph",
    );
  }
  return response.json();
}

export async function submitGGLSurvey(
  threadId: string,
  payload: SurveyRequest,
): Promise<SurveyResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/ggl/survey`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : error.detail?.message ?? "Failed to submit survey",
    );
  }
  return response.json();
}

export async function submitSurveyAnswers(
  threadId: string,
  payload: SurveyAnswersRequest,
): Promise<SurveyAnswersResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${threadId}/ggl/survey-answers`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : error.detail?.message ?? "Failed to submit survey answers",
    );
  }
  return response.json();
}
