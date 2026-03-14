"use client";

import { useCallback } from "react";

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
  const { gglState, refetch, isLoading, isEnabled } = useGGL();

  const handleNodeDoubleClick = useCallback(
    async (nodeId: string) => {
      if (!isEnabled) return;
      try {
        await setActiveNode(threadId, nodeId);
        await refetch();
      } catch (error) {
        console.error("Failed to set active node:", error);
      }
    },
    [threadId, refetch, isEnabled],
  );

  if (!isEnabled) {
    return null;
  }

  if (isLoading && !gglState) {
    return (
      <div className={cn("flex items-center justify-center p-4", className)}>
        <div className="text-sm text-muted-foreground">Loading graph...</div>
      </div>
    );
  }

  if (!gglState?.topic_graph) {
    return (
      <div className={cn("flex items-center justify-center p-4", className)}>
        <div className="text-sm text-muted-foreground">
          No topic graph yet. Start a conversation to create one.
        </div>
      </div>
    );
  }

  const { nodes, edges } = gglState.topic_graph;

  return (
    <div className={cn("relative overflow-auto p-4", className)}>
      <div className="min-w-[200px] min-h-[200px] relative">
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
            title={`Double-click to set as active: ${node.label}`}
          >
            {node.label}
          </div>
        ))}

        {edges.map((edge, index) => (
          <svg
            key={`edge-${index}`}
            className="absolute inset-0 pointer-events-none"
            style={{ width: "100%", height: "100%" }}
          >
            <line
              x1="50%"
              y1="50%"
              x2="50%"
              y2="50%"
              stroke="gray"
              strokeWidth={2}
              strokeDasharray={index % 2 === 0 ? "" : "4"}
            />
          </svg>
        ))}
      </div>

      {gglState.active_node_id && (
        <div className="mt-4 text-xs text-muted-foreground">
          Active:{" "}
          {nodes.find((n) => n.id === gglState.active_node_id)?.label ??
            gglState.active_node_id}
        </div>
      )}

      {gglState.current_path && gglState.current_path.length > 0 && (
        <div className="mt-2 text-xs text-muted-foreground">
          Path: {gglState.current_path.join(" → ")}
        </div>
      )}
    </div>
  );
}
