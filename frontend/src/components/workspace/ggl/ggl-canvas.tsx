"use client";

import { AlertCircle, BookOpen, Lightbulb } from "lucide-react";
import { useCallback, useMemo } from "react";

import { Button } from "@/components/ui/button";
import { setActiveNode } from "@/core/ggl/api";
import { useGGL } from "@/core/ggl/provider";
import { cn } from "@/lib/utils";

const NODE_STATE_COLORS = {
  unvisited: "bg-gray-200 border-gray-400",
  exploring: "bg-yellow-100 border-yellow-400",
  mastered: "bg-green-200 border-green-400",
  blurry: "bg-orange-100 border-orange-400",
  unknown: "bg-gray-100 border-gray-300",
} as const;

interface GGLCanvasProps {
  threadId: string;
  className?: string;
}

export function GGLCanvas({ threadId, className }: GGLCanvasProps) {
  const { gglState, refetch, isLoading, isEnabled, error } = useGGL();

  const handleNodeDoubleClick = useCallback(
    async (nodeId: string) => {
      if (!isEnabled) return;
      try {
        await setActiveNode(threadId, nodeId);
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

  // 错误状态提示
  if (error) {
    return (
      <div className={cn("flex flex-col items-center justify-center p-6 text-center", className)}>
        <AlertCircle className="h-8 w-8 text-destructive mb-2" />
        <div className="text-sm font-medium text-destructive mb-1">
          加载图谱失败
        </div>
        <div className="text-xs text-muted-foreground mb-3">
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
      <div className={cn("flex flex-col items-center justify-center p-6", className)}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mb-3" />
        <div className="text-sm text-muted-foreground">正在加载知识图谱...</div>
      </div>
    );
  }

  // 空图引导状态
  if (!gglState?.topic_graph) {
    return (
      <div className={cn("flex flex-col items-center justify-center p-6 text-center", className)}>
        <BookOpen className="h-12 w-12 text-muted-foreground/50 mb-3" />
        <div className="text-sm font-medium mb-2">知识图谱尚未创建</div>
        <div className="text-xs text-muted-foreground mb-4 leading-relaxed">
          当前会话还没有学习主题图谱。
          <br />
          开始对话后，AI 会引导你创建学习计划。
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/50 rounded-lg px-3 py-2">
          <Lightbulb className="h-4 w-4 text-yellow-500" />
          <span>提示：输入你想学习的主题名称</span>
        </div>
      </div>
    );
  }

  const { nodes, edges } = gglState.topic_graph;
  const layout = useMemo(() => {
    const width = 640;
    const height = 480;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.33;

    const positions = new Map<string, { x: number; y: number }>();
    if (nodes.length === 0) {
      return { width, height, positions };
    }
    nodes.forEach((node, index) => {
      const angle = (Math.PI * 2 * index) / nodes.length;
      positions.set(node.id, {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      });
    });
    return { width, height, positions };
  }, [nodes]);

  // 空节点但已有图谱结构
  if (nodes.length === 0) {
    return (
      <div className={cn("flex flex-col items-center justify-center p-6 text-center", className)}>
        <BookOpen className="h-10 w-10 text-muted-foreground/50 mb-3" />
        <div className="text-sm font-medium mb-2">图谱初始化中</div>
        <div className="text-xs text-muted-foreground">
          正在为你构建知识图谱，请稍候...
        </div>
      </div>
    );
  }

  return (
    <div className={cn("relative overflow-auto p-4", className)}>
      <div
        className="relative"
        style={{ width: layout.width, height: layout.height, minWidth: 200, minHeight: 200 }}
      >
        <svg
          className="absolute inset-0 pointer-events-none"
          style={{ width: "100%", height: "100%" }}
        >
          {edges.map((edge, index) => {
            const [fromId, toId] = edge;
            const from = layout.positions.get(fromId);
            const to = layout.positions.get(toId);
            if (!from || !to) {
              return null;
            }
            return (
              <line
                key={`edge-${index}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="gray"
                strokeWidth={2}
                strokeDasharray={index % 2 === 0 ? "" : "4"}
              />
            );
          })}
        </svg>

        {nodes.map((node) => (
          <div
            key={node.id}
            className={cn(
              "absolute cursor-pointer rounded-lg border-2 px-3 py-2 text-sm transition-colors",
              "hover:opacity-80",
              NODE_STATE_COLORS[node.state] || NODE_STATE_COLORS.unknown,
              gglState.active_node_id === node.id && "ring-2 ring-blue-500 ring-offset-2",
            )}
            onDoubleClick={() => handleNodeDoubleClick(node.id)}
            style={{
              left: (layout.positions.get(node.id)?.x ?? 0) - 48,
              top: (layout.positions.get(node.id)?.y ?? 0) - 18,
            }}
            title={`双击设为当前学习节点: ${node.label}`}
          >
            {node.label}
          </div>
        ))}
      </div>

      {gglState.active_node_id && (
        <div className="mt-4 text-xs text-muted-foreground">
          当前学习: {" "}
          {nodes.find((n) => n.id === gglState.active_node_id)?.label ??
            gglState.active_node_id}
        </div>
      )}

      {gglState.current_path && gglState.current_path.length > 0 && (
        <div className="mt-2 text-xs text-muted-foreground">
          学习路径: {gglState.current_path.join(" → ")}
        </div>
      )}
    </div>
  );
}
