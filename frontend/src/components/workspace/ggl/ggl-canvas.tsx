"use client";

import * as d3 from "d3";
import { AlertCircle, BookOpen, Lightbulb } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { initGGLGraph, setActiveNode, submitGGLSurvey } from "@/core/ggl/api";
import { useGGL } from "@/core/ggl/provider";
import { type TopicNode } from "@/core/ggl/types";
import { cn } from "@/lib/utils";

import { GGLNodeDetail } from "./node-detail";

const NODE_STATE_COLORS = {
  unvisited: "#e5e7eb",
  exploring: "#fef3c7",
  mastered: "#bbf7d0",
  blurry: "#fed7aa",
  unknown: "#f3f4f6",
} as const;

const NODE_STATE_STROKES = {
  unvisited: "#9ca3af",
  exploring: "#f59e0b",
  mastered: "#10b981",
  blurry: "#fb923c",
  unknown: "#d1d5db",
} as const;

interface SimulationNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  state: TopicNode["state"];
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimulationLink extends d3.SimulationLinkDatum<SimulationNode> {
  source: string | SimulationNode;
  target: string | SimulationNode;
}

interface GGLCanvasProps {
  threadId: string;
  className?: string;
}

export function GGLCanvas({ threadId, className }: GGLCanvasProps) {
  const { gglState, refetch, isLoading, isEnabled, error, highlightedNodeId, setHighlightedNodeId, scrollToMessage } = useGGL();
  const [detailNodeId, setDetailNodeId] = useState<string | null>(null);
  const [initTopic, setInitTopic] = useState("");
  const [initLoading, setInitLoading] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const [surveyOpen, setSurveyOpen] = useState(false);
  const [surveyLoading, setSurveyLoading] = useState(false);
  const [surveyError, setSurveyError] = useState<string | null>(null);
  const [surveyDraft, setSurveyDraft] = useState<Record<string, string>>({});

  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<d3.Simulation<SimulationNode, SimulationLink> | null>(null);

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

  // 准备力导向图数据
  const graphData = useMemo(() => {
    if (!gglState?.topic_graph) return null;

    const { nodes, edges } = gglState.topic_graph;
    const simNodes: SimulationNode[] = nodes.map((n) => ({
      id: n.id,
      label: n.label,
      state: n.state,
    }));

    const simLinks: SimulationLink[] = edges.map(([source, target]) => ({
      source,
      target,
    }));

    return { nodes: simNodes, links: simLinks };
  }, [gglState?.topic_graph]);

  // D3 力导向图初始化和更新
  useEffect(() => {
    if (!graphData || !svgRef.current || !containerRef.current) return;

    const svg = d3.select(svgRef.current);
    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

    // 清除之前的内容
    svg.selectAll("*").remove();

    // 创建缩放容器
    const g = svg.append("g");

    // 配置缩放行为
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform.toString());
      });

    svg.call(zoom);

    // 创建力导向仿真
    const simulation = d3
      .forceSimulation(graphData.nodes)
      .force(
        "link",
        d3
          .forceLink<SimulationNode, SimulationLink>(graphData.links)
          .id((d) => d.id)
          .distance(100),
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(50));

    simulationRef.current = simulation;

    // 绘制边（学习路径高亮）
    const currentPath = new Set(gglState?.current_path ?? []);
    const link = g
      .append("g")
      .selectAll("line")
      .data(graphData.links)
      .enter()
      .append("line")
      .attr("stroke", (d) => {
        const sourceId =
          typeof d.source === "string" ? d.source : d.source.id;
        const targetId =
          typeof d.target === "string" ? d.target : d.target.id;
        // 如果边的两端都在当前学习路径中，则高亮
        return currentPath.has(sourceId) && currentPath.has(targetId)
          ? "#3b82f6"
          : "#94a3b8";
      })
      .attr("stroke-width", (d) => {
        const sourceId =
          typeof d.source === "string" ? d.source : d.source.id;
        const targetId =
          typeof d.target === "string" ? d.target : d.target.id;
        return currentPath.has(sourceId) && currentPath.has(targetId) ? 3 : 2;
      })
      .attr("stroke-opacity", 0.6);

    // 绘制节点组
    const node = g
      .append("g")
      .selectAll("g")
      .data(graphData.nodes)
      .enter()
      .append("g")
      .call(
        d3
          .drag<SVGGElement, SimulationNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }),
      );

    // 节点圆形
    node
      .append("circle")
      .attr("r", 30)
      .attr("fill", (d) => NODE_STATE_COLORS[d.state] ?? "#f3f4f6")
      .attr("stroke", (d) => {
        // 高亮节点使用特殊颜色
        if (d.id === highlightedNodeId) return "#8b5cf6";
        // 活跃节点
        if (d.id === gglState?.active_node_id) return NODE_STATE_STROKES[d.state] ?? "#d1d5db";
        return NODE_STATE_STROKES[d.state] ?? "#d1d5db";
      })
      .attr("stroke-width", (d) => {
        if (d.id === highlightedNodeId) return 4;
        if (d.id === gglState?.active_node_id) return 4;
        return 2;
      })
      .attr("cursor", "pointer")
      .on("click", (_event, d) => {
        setDetailNodeId(d.id);
        // 触发滚动到相关消息（如果存在）
        // 暂时使用节点ID作为消息ID，实际需要从消息元数据中获取
        scrollToMessage(d.id);
      })
      .on("dblclick", (_event, d) => {
        void handleNodeDoubleClick(d.id);
      })
      .on("mouseenter", (_event, d) => {
        setHighlightedNodeId(d.id);
      })
      .on("mouseleave", () => {
        setHighlightedNodeId(null);
      });

    // 活跃节点脉动动画
    if (gglState?.active_node_id) {
      node
        .filter((d) => d.id === gglState.active_node_id)
        .append("circle")
        .attr("r", 30)
        .attr("fill", "none")
        .attr("stroke", "#3b82f6")
        .attr("stroke-width", 3)
        .attr("opacity", 0)
        .transition()
        .duration(1500)
        .ease(d3.easeQuadOut)
        .attr("r", 50)
        .attr("opacity", 0.5)
        .transition()
        .duration(0)
        .attr("r", 30)
        .attr("opacity", 0)
        .on("end", function repeat() {
          d3.select(this)
            .transition()
            .duration(1500)
            .ease(d3.easeQuadOut)
            .attr("r", 50)
            .attr("opacity", 0.5)
            .transition()
            .duration(0)
            .attr("r", 30)
            .attr("opacity", 0)
            .on("end", repeat);
        });
    }

    // 节点文本标签
    node
      .append("text")
      .text((d) => d.label)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("font-size", "12px")
      .attr("fill", "#1f2937")
      .attr("pointer-events", "none")
      .style("user-select", "none");

    // 更新节点和边的位置
    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimulationNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimulationNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimulationNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimulationNode).y ?? 0);

      node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => {
      simulation.stop();
    };
  }, [graphData, gglState?.active_node_id, gglState?.current_path, highlightedNodeId, handleNodeDoubleClick, scrollToMessage, setHighlightedNodeId]);

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
        <div className="mt-4 w-full max-w-sm space-y-2">
          <Input
            value={initTopic}
            onChange={(e) => setInitTopic(e.target.value)}
            placeholder="例如：机器学习基础"
          />
          <Button
            className="w-full"
            disabled={initLoading || initTopic.trim().length === 0}
            onClick={async () => {
              setInitLoading(true);
              setInitError(null);
              try {
                await initGGLGraph(threadId, { topic: initTopic.trim() });
                await refetch();
              } catch (e) {
                const message =
                  e instanceof Error ? e.message : "初始化图谱失败";
                setInitError(message);
              } finally {
                setInitLoading(false);
              }
            }}
          >
            {initLoading ? "初始化中..." : "初始化图谱"}
          </Button>
          {initError && (
            <div className="text-xs text-destructive">{initError}</div>
          )}
        </div>
      </div>
    );
  }

  const { nodes = [] } = gglState?.topic_graph ?? {};
  const nodeStates = [
    "unvisited",
    "exploring",
    "mastered",
    "blurry",
    "unknown",
  ] as const;

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
    <div className={cn("flex flex-col h-full", className)}>
      <div ref={containerRef} className="flex-1 relative overflow-hidden bg-background">
        <svg
          ref={svgRef}
          className="w-full h-full"
          style={{ cursor: "grab" }}
        />
      </div>

      <div className="p-4 border-t space-y-2">
        {gglState.active_node_id && (
          <div className="text-xs text-muted-foreground">
            当前学习:{" "}
            {nodes.find((n) => n.id === gglState.active_node_id)?.label ??
              gglState.active_node_id}
          </div>
        )}

        {gglState.current_path && gglState.current_path.length > 0 && (
          <div className="text-xs text-muted-foreground">
            学习路径: {gglState.current_path.join(" → ")}
          </div>
        )}

        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            const initialDraft: Record<string, string> = {};
            nodes.forEach((node) => {
              initialDraft[node.id] = node.state;
            });
            setSurveyDraft(initialDraft);
            setSurveyError(null);
            setSurveyOpen(true);
          }}
        >
          更新学习状态（Survey）
        </Button>
      </div>
      <Dialog open={surveyOpen} onOpenChange={setSurveyOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>学习状态调研</DialogTitle>
          </DialogHeader>
          <div className="max-h-[50vh] overflow-auto pr-1 space-y-2">
            {nodes.map((node) => (
              <div
                key={node.id}
                className="grid grid-cols-[1fr_180px] items-center gap-3 border rounded-md p-2"
              >
                <div className="text-sm">
                  <div className="font-medium">{node.label}</div>
                  <div className="text-xs text-muted-foreground">{node.id}</div>
                </div>
                <select
                  className="h-9 rounded-md border px-2 text-sm bg-background"
                  value={surveyDraft[node.id] ?? node.state}
                  onChange={(e) =>
                    setSurveyDraft((prev) => ({
                      ...prev,
                      [node.id]: e.target.value,
                    }))
                  }
                >
                  {nodeStates.map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          {surveyError && (
            <div className="text-xs text-destructive">{surveyError}</div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <Button
              variant="outline"
              onClick={() => setSurveyOpen(false)}
              disabled={surveyLoading}
            >
              取消
            </Button>
            <Button
              disabled={surveyLoading}
              onClick={async () => {
                setSurveyLoading(true);
                setSurveyError(null);
                try {
                  await submitGGLSurvey(threadId, {
                    assessments: nodes.map((node) => ({
                      node_id: node.id,
                      state: (surveyDraft[node.id] ?? node.state) as
                        | "unvisited"
                        | "exploring"
                        | "mastered"
                        | "blurry"
                        | "unknown",
                    })),
                    expected_version: gglState.topic_graph_version ?? undefined,
                  });
                  await refetch();
                  setSurveyOpen(false);
                } catch (e) {
                  const message =
                    e instanceof Error ? e.message : "提交 survey 失败";
                  setSurveyError(message);
                } finally {
                  setSurveyLoading(false);
                }
              }}
            >
              {surveyLoading ? "提交中..." : "提交"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <GGLNodeDetail
        threadId={threadId}
        nodeId={detailNodeId}
        nodeLabel={nodes.find((n) => n.id === detailNodeId)?.label}
        open={detailNodeId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDetailNodeId(null);
          }
        }}
      />
    </div>
  );
}
