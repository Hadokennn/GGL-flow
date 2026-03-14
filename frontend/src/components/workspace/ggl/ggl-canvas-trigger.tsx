"use client";

import { NetworkIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/workspace/tooltip";
import { useGGL } from "@/core/ggl/provider";

interface GGLCanvasTriggerProps {
  isOpen: boolean;
  onToggle: () => void;
}

export function GGLCanvasTrigger({ isOpen, onToggle }: GGLCanvasTriggerProps) {
  const { isEnabled, isLoading } = useGGL();

  if (!isEnabled) {
    return null;
  }

  return (
    <Tooltip content={isOpen ? "Close GGL Canvas" : "Open GGL Canvas"}>
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggle}
        className={isOpen ? "bg-accent" : ""}
        disabled={isLoading}
      >
        <NetworkIcon className="size-4" />
        <span className="ml-2 text-xs">GGL</span>
      </Button>
    </Tooltip>
  );
}
