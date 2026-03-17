"use client";

import {
  Background,
  type Edge,
  Handle,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import { AlertCircle, BookOpen, CheckCircle2, Lightbulb, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { setActiveNode } from "@/core/ggl/api";
import { useGGL } from "@/core/ggl/provider";
import type { KnowledgeCard, TopicNode as TopicNodeType } from "@/core/ggl/types";
import { cn } from "@/lib/utils";

import "@xyflow/react/dist/style.css";

const NODE_STATE_COLORS: Record<string, string> = {
  unvisited: "bg-gray-200 border-gray-400",
  exploring: "bg-yellow-100 border-yellow-400",
  mastered: "bg-green-200 border-green-400",
  blurry: "bg-orange-100 border-orange-400",
  unknown: "bg-gray-100 border-gray-300",
};

type TopicNodeData = Pick<TopicNodeType, "label" | "state"> & {
  active?: boolean;
  hasCard?: boolean;
};

function TopicNode({ data, selected }: NodeProps<Node<TopicNodeData, "topic">>) {
  const state = data?.state ?? "unknown";
  const label = data?.label ?? "";
  const isActive = data?.active ?? false;
  const hasCard = data?.hasCard ?? false;

  return (
    <div
      className={cn(
        "cursor-pointer rounded-lg border-2 px-3 py-2 text-sm transition-colors hover:opacity-80",
        NODE_STATE_COLORS[state] ?? NODE_STATE_COLORS.unknown,
        (selected || isActive) && "ring-2 ring-blue-500 ring-offset-2",
      )}
    >
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
      <div className="flex items-center gap-1">
        {state === "mastered" && hasCard && (
          <CheckCircle2 className="h-3 w-3 shrink-0 text-green-600" />
        )}
        {label}
      </div>
    </div>
  );
}

const nodeTypes = { topic: TopicNode };

// ---------------------------------------------------------------------------
// KnowledgeCardPreview
// ---------------------------------------------------------------------------

interface KnowledgeCardPreviewProps {
  nodeLabel: string;
  card: KnowledgeCard;
  onClose: () => void;
}

function KnowledgeCardPreview({ nodeLabel, card, onClose }: KnowledgeCardPreviewProps) {
  return (
    <div className="absolute bottom-0 left-0 right-0 z-10 rounded-t-xl border bg-background shadow-lg">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium">{nodeLabel}</span>
        </div>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="max-h-72 overflow-y-auto px-4 py-3 space-y-3 text-xs">
        {card.summary && (
          <p className="text-muted-foreground leading-relaxed">{card.summary}</p>
        )}
        {card.keyPoints?.length > 0 && (
          <div>
            <div className="mb-1 font-semibold text-foreground">关键知识点</div>
            <ul className="space-y-1">
              {card.keyPoints.map((point, i) => (
                <li key={i} className="flex gap-1.5 text-muted-foreground">
                  <span className="mt-0.5 shrink-0 text-primary">•</span>
                  {point}
                </li>
              ))}
            </ul>
          </div>
        )}
        {card.examples?.length > 0 && (
          <div>
            <div className="mb-1 font-semibold text-foreground">示例</div>
            <ul className="space-y-1">
              {card.examples.map((ex, i) => (
                <li key={i} className="text-muted-foreground">{ex}</li>
              ))}
            </ul>
          </div>
        )}
        {card.commonMistakes?.length > 0 && (
          <div>
            <div className="mb-1 font-semibold text-foreground">常见误区</div>
            <ul className="space-y-1">
              {card.commonMistakes.map((m, i) => (
                <li key={i} className="flex gap-1.5 text-muted-foreground">
                  <span className="mt-0.5 shrink-0 text-destructive">!</span>
                  {m}
                </li>
              ))}
            </ul>
          </div>
        )}
        {card.relatedConcepts?.length > 0 && (
          <div>
            <div className="mb-1 font-semibold text-foreground">相关概念</div>
            <div className="flex flex-wrap gap-1">
              {card.relatedConcepts.map((c, i) => (
                <span key={i} className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const NODE_WIDTH = 96;
const NODE_HEIGHT = 36;
const LEVEL_GAP = 80;
const SIBLING_GAP = 48;

/** Mind-map style hierarchical layout: root at top, children below, spread horizontally. */
function mindMapLayout(
  nodes: TopicNodeType[],
  edges: [string, string][],
  activeNodeId: string | null,
  currentPath: string[] | null,
) {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const childrenMap = new Map<string, string[]>();
  for (const [source, target] of edges) {
    if (nodeMap.has(source) && nodeMap.has(target)) {
      const list = childrenMap.get(source) ?? [];
      if (!list.includes(target)) list.push(target);
      childrenMap.set(source, list);
    }
  }

  const roots: string[] = currentPath?.[0]
    ? [currentPath[0]]
    : nodes.filter((n) => !edges.some(([, t]) => t === n.id)).map((n) => n.id);
  if (roots.length === 0 && nodes.length > 0) roots.push(nodes[0]!.id);

  const depthMap = new Map<string, number>();
  const visit = (id: string, d: number) => {
    if (depthMap.has(id)) return;
    depthMap.set(id, d);
    for (const c of childrenMap.get(id) ?? []) visit(c, d + 1);
  };
  for (const r of roots) visit(r, 0);
  for (const n of nodes) if (!depthMap.has(n.id)) depthMap.set(n.id, 999);

  const byLevel = new Map<number, string[]>();
  for (const [id, d] of depthMap) {
    if (d < 999) {
      const list = byLevel.get(d) ?? [];
      list.push(id);
      byLevel.set(d, list);
    }
  }

  const positions = new Map<string, { x: number; y: number }>();
  let maxWidth = 0;
  const levels = [...byLevel.entries()].sort((a, b) => a[0] - b[0]);
  for (const [level, ids] of levels) {
    const totalW = ids.length * NODE_WIDTH + (ids.length - 1) * SIBLING_GAP;
    maxWidth = Math.max(maxWidth, totalW);
    const startX = -totalW / 2 + NODE_WIDTH / 2 + SIBLING_GAP / 2;
    ids.forEach((id, i) => {
      positions.set(id, {
        x: startX + i * (NODE_WIDTH + SIBLING_GAP),
        y: level * (NODE_HEIGHT + LEVEL_GAP),
      });
    });
  }

  const orphanIds = nodes.filter((n) => !positions.has(n.id)).map((n) => n.id);
  const maxLevel = levels.length ? Math.max(...levels.map(([l]) => l)) : 0;
  orphanIds.forEach((id, i) => {
    positions.set(id, {
      x: -maxWidth / 2 + NODE_WIDTH / 2 + i * (NODE_WIDTH + SIBLING_GAP),
      y: (maxLevel + 1) * (NODE_HEIGHT + LEVEL_GAP),
    });
  });

  const minX = Math.min(...[...positions.values()].map((p) => p.x));
  const minY = Math.min(...[...positions.values()].map((p) => p.y));
  const offsetX = -minX + 24;
  const offsetY = -minY + 24;

  return nodes.map((node) => {
    const pos = positions.get(node.id) ?? { x: 0, y: 0 };
    return {
      id: node.id,
      type: "topic" as const,
      position: {
        x: pos.x + offsetX - NODE_WIDTH / 2,
        y: pos.y + offsetY - NODE_HEIGHT / 2,
      },
      data: {
        label: node.label,
        state: node.state,
        active: node.id === activeNodeId,
      },
    };
  });
}

interface KnowledgeMapProps {
  threadId: string;
  className?: string;
}

function KnowledgeMapInner({ threadId, className }: KnowledgeMapProps) {
  const { gglState, refetch, isLoading, isEnabled, error } = useGGL();
  const [previewNodeId, setPreviewNodeId] = useState<string | null>(null);

  type TopicFlowNode = Node<TopicNodeData, "topic">;
  const [nodes, setNodes, onNodesChange] = useNodesState<TopicFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const knowledgeCards = gglState?.knowledge_cards ?? null;

  const flowNodes = useMemo(() => {
    if (!gglState?.topic_graph?.nodes.length) return [];
    return mindMapLayout(
      gglState.topic_graph.nodes,
      gglState.topic_graph.edges ?? [],
      gglState.active_node_id ?? null,
      gglState.current_path ?? null,
    ).map((n) => ({
      ...n,
      data: {
        ...n.data,
        hasCard: Boolean(knowledgeCards?.[n.id]),
      },
    }));
  }, [
    gglState?.topic_graph?.nodes,
    gglState?.topic_graph?.edges,
    gglState?.active_node_id,
    gglState?.current_path,
    knowledgeCards,
  ]);

  const flowEdges = useMemo(() => {
    if (!gglState?.topic_graph?.edges?.length) return [];
    const nodeIds = new Set(
      gglState.topic_graph.nodes.map((n) => n.id),
    );
    return gglState.topic_graph.edges
      .filter(([source, target]) => nodeIds.has(source) && nodeIds.has(target))
      .map(([source, target], i) => ({
        id: `e-${source}-${target}-${i}`,
        source,
        target,
      }));
  }, [gglState?.topic_graph?.edges, gglState?.topic_graph?.nodes]);

  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const card = knowledgeCards?.[node.id];
      if (card) {
        setPreviewNodeId((prev) => (prev === node.id ? null : node.id));
      }
    },
    [knowledgeCards],
  );

  const handleNodeDoubleClick = useCallback(
    async (_: React.MouseEvent, node: Node) => {
      if (!isEnabled) return;
      setPreviewNodeId(null);
      try {
        await setActiveNode(threadId, node.id);
        await refetch();
      } catch (err) {
        console.error("Failed to set active node:", err);
      }
    },
    [threadId, refetch, isEnabled],
  );

  if (!isEnabled) {
    return null;
  }

  if (error) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center p-6 text-center",
          className,
        )}
      >
        <AlertCircle className="mb-2 h-8 w-8 text-destructive" />
        <div className="mb-1 text-sm font-medium text-destructive">
          加载图谱失败
        </div>
        <div className="mb-3 text-xs text-muted-foreground">
          {error.message || "请检查网络连接后重试"}
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          重试
        </Button>
      </div>
    );
  }

  if (isLoading && !gglState) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center p-6",
          className,
        )}
      >
        <div className="mb-3 h-8 w-8 animate-spin rounded-full border-b-2 border-primary" />
        <div className="text-sm text-muted-foreground">正在加载知识图谱...</div>
      </div>
    );
  }

  if (!gglState?.topic_graph) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center p-6 text-center",
          className,
        )}
      >
        <BookOpen className="mb-3 h-12 w-12 text-muted-foreground/50" />
        <div className="mb-2 text-sm font-medium">知识图谱尚未创建</div>
        <div className="mb-4 text-xs leading-relaxed text-muted-foreground">
          当前会话还没有学习主题图谱。
          <br />
          开始对话后，AI 会引导你创建学习计划。
        </div>
        <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          <Lightbulb className="h-4 w-4 text-yellow-500" />
          <span>提示：输入你想学习的主题名称</span>
        </div>
      </div>
    );
  }

  const { nodes: topicNodes } = gglState.topic_graph;

  if (topicNodes.length === 0) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center p-6 text-center",
          className,
        )}
      >
        <BookOpen className="mb-3 h-10 w-10 text-muted-foreground/50" />
        <div className="mb-2 text-sm font-medium">图谱初始化中</div>
        <div className="text-xs text-muted-foreground">
          正在为你构建知识图谱，请稍候...
        </div>
      </div>
    );
  }

  return (
    <div className={cn("relative flex min-h-0 flex-1 flex-col", className)}>
      <div className="min-h-0 flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeDoubleClick}
          nodeTypes={nodeTypes}
          nodesDraggable={true}
          nodesConnectable={true}
          elementsSelectable={true}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          panOnScroll
          zoomOnScroll
          zoomOnPinch
          minZoom={0.3}
          maxZoom={1.5}
          proOptions={{ hideAttribution: true }}
        >
          <Background className="bg-muted/30" />
        </ReactFlow>
      </div>

      {gglState.active_node_id && (
        <div className="mt-4 shrink-0 text-xs text-muted-foreground">
          当前学习:{" "}
          {topicNodes.find((n) => n.id === gglState.active_node_id)?.label ??
            gglState.active_node_id}
        </div>
      )}

      {gglState.current_path && gglState.current_path.length > 0 && (
        <div className="mt-2 shrink-0 text-xs text-muted-foreground">
          学习路径: {gglState.current_path.join(" → ")}
        </div>
      )}

      {previewNodeId && knowledgeCards?.[previewNodeId] && (() => {
        const node = topicNodes.find((n) => n.id === previewNodeId);
        return (
          <KnowledgeCardPreview
            nodeLabel={node?.label ?? previewNodeId}
            card={knowledgeCards[previewNodeId]!}
            onClose={() => setPreviewNodeId(null)}
          />
        );
      })()}
    </div>
  );
}

export function KnowledgeMap(props: KnowledgeMapProps) {
  return (
    <ReactFlowProvider>
      <KnowledgeMapInner {...props} />
    </ReactFlowProvider>
  );
}
