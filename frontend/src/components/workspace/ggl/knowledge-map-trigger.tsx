"use client";

import { NetworkIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useRightPanel } from "@/components/workspace/chats/right-panel-context";
import { Tooltip } from "@/components/workspace/tooltip";
import { useGGL } from "@/core/ggl/provider";

export function KnowledgeMapTrigger() {
  const { isEnabled, isLoading } = useGGL();
  const rightPanel = useRightPanel();

  if (!isEnabled || !rightPanel?.gglEnabled) {
    return null;
  }

  const isOpen = rightPanel.view === "ggl";

  return (
    <Tooltip content={isOpen ? "关闭知识图谱" : "打开知识图谱"}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => (isOpen ? rightPanel.close() : rightPanel.openGGL())}
        className={isOpen ? "bg-accent" : ""}
        disabled={isLoading}
      >
        <NetworkIcon className="size-4" />
        <span className="ml-2 text-xs">图谱</span>
      </Button>
    </Tooltip>
  );
}
