"use client";

import {
  Background,
  type Edge,
  type Node,
  type NodeProps,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
} from "@xyflow/react";
import { AlertCircle, BookOpen, Lightbulb } from "lucide-react";
import { useCallback, useEffect, useMemo } from "react";

import { Button } from "@/components/ui/button";
import { setActiveNode } from "@/core/ggl/api";
import { useGGL } from "@/core/ggl/provider";
import type { TopicNode as TopicNodeType } from "@/core/ggl/types";
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
};

function TopicNode({ data, selected }: NodeProps<Node<TopicNodeData, "topic">>) {
  const state = data?.state ?? "unknown";
  const label = data?.label ?? "";
  const isActive = data?.active ?? false;

  return (
    <div
      className={cn(
        "cursor-pointer rounded-lg border-2 px-3 py-2 text-sm transition-colors hover:opacity-80",
        NODE_STATE_COLORS[state] ?? NODE_STATE_COLORS.unknown,
        (selected || isActive) && "ring-2 ring-blue-500 ring-offset-2",
      )}
    >
      {label}
    </div>
  );
}

const nodeTypes = { topic: TopicNode };

function circularLayout(
  nodes: TopicNodeType[],
  activeNodeId: string | null,
) {
  const width = 640;
  const height = 480;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.33;

  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / nodes.length;
    return {
      id: node.id,
      type: "topic" as const,
      position: {
        x: centerX + radius * Math.cos(angle) - 48,
        y: centerY + radius * Math.sin(angle) - 18,
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

  type TopicFlowNode = Node<TopicNodeData, "topic">;
  const [nodes, setNodes, onNodesChange] = useNodesState<TopicFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const flowNodes = useMemo(() => {
    if (!gglState?.topic_graph?.nodes.length) return [];
    return circularLayout(
      gglState.topic_graph.nodes,
      gglState.active_node_id ?? null,
    );
  }, [gglState?.topic_graph?.nodes, gglState?.active_node_id]);

  const flowEdges = useMemo(() => {
    if (!gglState?.topic_graph?.edges.length) return [];
    return gglState.topic_graph.edges.map(([source, target], i) => ({
      id: `e-${source}-${target}-${i}`,
      source,
      target,
    }));
  }, [gglState?.topic_graph?.edges]);

  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  const handleNodeDoubleClick = useCallback(
    async (_: React.MouseEvent, node: Node) => {
      if (!isEnabled) return;
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
          onNodeDoubleClick={handleNodeDoubleClick}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
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
