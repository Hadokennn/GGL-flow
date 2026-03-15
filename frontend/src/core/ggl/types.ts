export interface TopicNode {
  id: string;
  label: string;
  state: "unvisited" | "exploring" | "mastered" | "blurry" | "unknown";
}

export interface TopicGraph {
  nodes: TopicNode[];
  edges: [string, string][];
}

export interface KnowledgeCard {
  summary: string;
  keyPoints: string[];
  examples: string[];
  commonMistakes: string[];
  relatedConcepts: string[];
}

export interface GGLState {
  active_node_id: string | null;
  topic_graph: TopicGraph | null;
  topic_graph_version: number | null;
  digression_stack: string[] | null;
  current_path: string[] | null;
  knowledge_cards: Record<string, KnowledgeCard> | null;
}

export interface GGLGraphResponse {
  active_node_id: string | null;
  topic_graph: TopicGraph | null;
  topic_graph_version: number | null;
  digression_stack: string[] | null;
  current_path: string[] | null;
  knowledge_cards: Record<string, KnowledgeCard> | null;
}

export interface ActiveNodeUpdate {
  node_id: string;
}

export interface ActiveNodeResponse {
  active_node_id: string;
  topic_graph_version: number | null;
}

export interface KnowledgeCardResponse {
  node_id: string;
  knowledge_card: KnowledgeCard;
}

export interface InitGraphRequest {
  topic: string;
  expected_version?: number;
  use_llm?: boolean;
  model_name?: string;
}

export interface InitGraphResponse {
  topic_graph: TopicGraph;
  topic_graph_version: number;
  survey?: SurveyData;
}

export interface SurveyData {
  questions: SurveyQuestion[];
}

export interface SurveyQuestion {
  id: string;
  question: string;
  related_nodes?: string[];
  evaluation_hints?: {
    mastered: string;
    blurry: string;
    unknown: string;
  };
}

export interface SurveyItem {
  node_id: string;
  state: TopicNode["state"];
}

export interface SurveyRequest {
  assessments: SurveyItem[];
  expected_version?: number;
}

export interface SurveyResponse {
  topic_graph: TopicGraph;
  topic_graph_version: number;
}

export interface SurveyAnswersRequest {
  responses: Record<string, string>;
  expected_version?: number;
}

export interface SurveyAnswersResponse {
  topic_graph: TopicGraph;
  topic_graph_version: number;
  assessments: Record<string, string>;
}

export interface AgentVariantInfo {
  name: string;
  label: string;
  description: string;
}

export interface AgentVariantsResponse {
  variants: AgentVariantInfo[];
}
