import { FilesIcon, XIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GroupImperativeHandle } from "react-resizable-panels";

import { ConversationEmptyState } from "@/components/ai-elements/conversation";
import { Button } from "@/components/ui/button";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { env } from "@/env";
import { cn } from "@/lib/utils";

import {
  ArtifactFileDetail,
  ArtifactFileList,
  useArtifacts,
} from "../artifacts";
import { KnowledgeMap } from "../ggl";
import { useThread } from "../messages/context";

import { RightPanelProvider, useRightPanel } from "./right-panel-context";

const CLOSE_MODE = { chat: 100, "right-panel": 0 };
const OPEN_MODE = { chat: 60, "right-panel": 40 };

const ChatBoxInner: React.FC<{
  children: React.ReactNode;
  threadId: string;
}> = ({ children, threadId }) => {
  const { thread } = useThread();
  const threadIdRef = useRef(threadId);
  const layoutRef = useRef<GroupImperativeHandle>(null);

  const rightPanel = useRightPanel();
  if (!rightPanel) {
    throw new Error("ChatBoxInner must be used within RightPanelProvider");
  }
  const { view: rightPanelView, close: closeRightPanel } = rightPanel;
  const {
    artifacts,
    setArtifacts,
    select: selectArtifact,
    deselect,
    selectedArtifact,
  } = useArtifacts();

  const [autoSelectFirstArtifact, setAutoSelectFirstArtifact] = useState(true);
  useEffect(() => {
    if (threadIdRef.current !== threadId) {
      threadIdRef.current = threadId;
      deselect();
    }

    // Update artifacts from the current thread
    setArtifacts(thread.values.artifacts);

    // DO NOT automatically deselect the artifact when switching threads, because the artifacts auto discovering is not work now.
    // if (
    //   selectedArtifact &&
    //   !thread.values.artifacts?.includes(selectedArtifact)
    // ) {
    //   deselect();
    // }

    if (
      env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" &&
      autoSelectFirstArtifact
    ) {
      if (thread?.values?.artifacts?.length > 0) {
        setAutoSelectFirstArtifact(false);
        selectArtifact(thread.values.artifacts[0]!);
      }
    }
  }, [
    threadId,
    autoSelectFirstArtifact,
    deselect,
    selectArtifact,
    selectedArtifact,
    setArtifacts,
    thread.values.artifacts,
  ]);

  const panelOpen = rightPanelView !== null;
  const artifactPanelOpen = useMemo(() => {
    if (env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true") {
      return panelOpen && (rightPanelView === "ggl" || (artifacts?.length ?? 0) > 0);
    }
    return panelOpen;
  }, [panelOpen, rightPanelView, artifacts]);

  useEffect(() => {
    if (layoutRef.current) {
      if (artifactPanelOpen) {
        layoutRef.current.setLayout(OPEN_MODE);
      } else {
        layoutRef.current.setLayout(CLOSE_MODE);
      }
    }
  }, [artifactPanelOpen]);

  return (
    <ResizablePanelGroup
      orientation="horizontal"
      defaultLayout={{ chat: 100, "right-panel": 0 }}
      groupRef={layoutRef}
    >
      <ResizablePanel className="relative" defaultSize={100} id="chat">
        {children}
      </ResizablePanel>
      <ResizableHandle
        className={cn(
          "opacity-33 hover:opacity-100",
          !artifactPanelOpen && "pointer-events-none opacity-0",
        )}
      />
      <ResizablePanel
        className={cn(
          "transition-all duration-300 ease-in-out",
          !panelOpen && "opacity-0",
        )}
        id="right-panel"
      >
        <div
          className={cn(
            "relative flex h-full flex-col p-4 transition-transform duration-300 ease-in-out",
            artifactPanelOpen ? "translate-x-0" : "translate-x-full",
          )}
        >
          <div className="absolute right-1 top-1 z-30">
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={closeRightPanel}
            >
              <XIcon />
            </Button>
          </div>
          {rightPanelView === "ggl" ? (
            <KnowledgeMap className="min-h-0 flex-1" threadId={threadId} />
          ) : rightPanelView === "artifacts" ? (
            selectedArtifact ? (
              <ArtifactFileDetail
                className="size-full"
                filepath={selectedArtifact}
                threadId={threadId}
              />
            ) : (
              <div className="relative flex size-full justify-center">
                {thread.values.artifacts?.length === 0 ? (
                  <ConversationEmptyState
                    icon={<FilesIcon />}
                    title="No artifact selected"
                    description="Select an artifact to view its details"
                  />
                ) : (
                  <div className="flex size-full max-w-(--container-width-sm) flex-col justify-center p-4 pt-8">
                    <header className="shrink-0">
                      <h2 className="text-lg font-medium">Artifacts</h2>
                    </header>
                    <main className="min-h-0 grow">
                      <ArtifactFileList
                        className="max-w-(--container-width-sm) p-4 pt-12"
                        files={thread.values.artifacts ?? []}
                        threadId={threadId}
                      />
                    </main>
                  </div>
                )}
              </div>
            )
          ) : null}
        </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
};

const ChatBox: React.FC<{
  children: React.ReactNode;
  threadId: string;
  gglEnabled?: boolean;
}> = ({ children, threadId, gglEnabled = false }) => (
  <RightPanelProvider gglEnabled={gglEnabled}>
    <ChatBoxInner threadId={threadId}>
      {children}
    </ChatBoxInner>
  </RightPanelProvider>
);

export { ChatBox };
