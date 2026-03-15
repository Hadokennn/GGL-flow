"use client";

import { useEffect, useState } from "react";

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { fetchKnowledgeCard } from "@/core/ggl/api";
import type { KnowledgeCard } from "@/core/ggl/types";

interface GGLNodeDetailProps {
  threadId: string;
  nodeId: string | null;
  nodeLabel?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GGLNodeDetail({ threadId, nodeId, nodeLabel, open, onOpenChange }: GGLNodeDetailProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [card, setCard] = useState<KnowledgeCard | null>(null);

  useEffect(() => {
    if (!open || !nodeId) {
      return;
    }
    setLoading(true);
    setError(null);
    fetchKnowledgeCard(threadId, nodeId)
      .then((res) => setCard(res.knowledge_card))
      .catch((e: unknown) => {
        const message = e instanceof Error ? e.message : "加载知识卡片失败";
        setError(message);
        setCard(null);
      })
      .finally(() => setLoading(false));
  }, [nodeId, open, threadId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{nodeLabel ? `知识卡片：${nodeLabel}` : "知识卡片"}</DialogTitle>
        </DialogHeader>
        {loading && <div className="text-sm text-muted-foreground">加载中...</div>}
        {!loading && error && <div className="text-sm text-destructive">{error}</div>}
        {!loading && !error && card && (
          <div className="space-y-4 text-sm">
            <section>
              <h4 className="font-semibold mb-1">总结</h4>
              <p className="text-muted-foreground whitespace-pre-wrap">{card.summary}</p>
            </section>
            <section>
              <h4 className="font-semibold mb-1">要点</h4>
              <ul className="list-disc pl-5 space-y-1">
                {card.keyPoints.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            {card.examples.length > 0 && (
              <section>
                <h4 className="font-semibold mb-1">例子</h4>
                <ul className="list-disc pl-5 space-y-1">
                  {card.examples.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            )}
            {card.commonMistakes.length > 0 && (
              <section>
                <h4 className="font-semibold mb-1">常见误区</h4>
                <ul className="list-disc pl-5 space-y-1">
                  {card.commonMistakes.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

