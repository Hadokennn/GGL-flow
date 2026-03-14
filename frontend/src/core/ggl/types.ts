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

export interface AgentVariantInfo {
  name: string;
  label: string;
  description: string;
}

export interface AgentVariantsResponse {
  variants: AgentVariantInfo[];
}
