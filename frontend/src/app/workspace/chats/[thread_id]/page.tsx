"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { type PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { ArtifactTrigger } from "@/components/workspace/artifacts";
import {
  ChatBox,
  useSpecificChatMode,
  useThreadChat,
} from "@/components/workspace/chats";
import { useRightPanel } from "@/components/workspace/chats/right-panel-context";
import { KnowledgeMapTrigger } from "@/components/workspace/ggl";
import { InputBox } from "@/components/workspace/input-box";
import { MessageList } from "@/components/workspace/messages";
import {
  type PendingCheckpoint,
  ThreadContext,
} from "@/components/workspace/messages/context";
import { ThreadTitle } from "@/components/workspace/thread-title";
import { TodoList } from "@/components/workspace/todo-list";
import { Welcome } from "@/components/workspace/welcome";
import { useGGLState } from "@/core/ggl/provider";
import { GGLProvider } from "@/core/ggl/provider";
import type { GGLState } from "@/core/ggl/types";
import { useI18n } from "@/core/i18n/hooks";
import { useNotification } from "@/core/notification/hooks";
import { useLocalSettings } from "@/core/settings";
import { fetchThreadInfo } from "@/core/threads/api";
import { useThreadStream } from "@/core/threads/hooks";
import { textOfMessage } from "@/core/threads/utils";
import { env } from "@/env";
import { cn } from "@/lib/utils";

/**
 * Watches gglState inside RightPanelProvider context and auto-opens the
 * Knowledge Map panel when topic_graph first becomes available.
 */
function GGLAutoOpen() {
  const gglState = useGGLState();
  const rightPanel = useRightPanel();
  const hasAutoOpened = useRef(false);

  useEffect(() => {
    if (
      !hasAutoOpened.current &&
      gglState?.topic_graph &&
      rightPanel?.view === null
    ) {
      hasAutoOpened.current = true;
      rightPanel.openGGL();
    }
  }, [gglState?.topic_graph, rightPanel]);

  return null;
}

function ChatContentWithThread({
  threadId,
  isNewThread,
  isMock,
  agentVariant,
}: {
  threadId: string;
  isNewThread: boolean;
  isMock: boolean;
  agentVariant: string | null;
}) {
  const { t } = useI18n();
  const [settings, setSettings] = useLocalSettings();
  const { setIsNewThread } = useThreadChat();
  const { showNotification } = useNotification();
  const pendingCheckpointRef = useRef<PendingCheckpoint | null>(null);

  const [thread, sendMessage] = useThreadStream({
    threadId: isNewThread ? undefined : threadId,
    context: settings.context,
    isMock,
    pendingCheckpointRef,
    onStart: () => {
      setIsNewThread(false);
      history.replaceState(null, "", `/workspace/chats/${threadId}`);
    },
    onFinish: (state) => {
      if (document.hidden || !document.hasFocus()) {
        let body = "Conversation finished";
        const lastMessage = state.messages.at(-1);
        if (lastMessage) {
          const textContent = textOfMessage(lastMessage);
          if (textContent) {
            body =
              textContent.length > 200
                ? textContent.substring(0, 200) + "..."
                : textContent;
          }
        }
        showNotification(state.title, { body });
      }
    },
  });

  const effectiveAgentVariant =
    (thread?.values?.agent_variant as string | null | undefined) ?? agentVariant;
  const gglEnabled = effectiveAgentVariant === "ggl";

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      void sendMessage(threadId, message);
    },
    [sendMessage, threadId],
  );
  const handleStop = useCallback(async () => {
    await thread.stop();
  }, [thread]);

  return (
    <ThreadContext.Provider value={{ thread, isMock, pendingCheckpointRef }}>
      <GGLProvider
        threadId={threadId}
        enabled={gglEnabled}
        streamedState={(thread?.values?.ggl as GGLState | null | undefined) ?? null}
      >
        <ChatBox gglEnabled={gglEnabled} threadId={threadId}>
          <GGLAutoOpen />
          <div className="relative flex size-full min-h-0 justify-between">
            <header
            className={cn(
              "absolute top-0 right-0 left-0 z-30 flex h-12 shrink-0 items-center px-4",
              isNewThread
                ? "bg-background/0 backdrop-blur-none"
                : "bg-background/80 shadow-xs backdrop-blur",
            )}
          >
            <div className="flex w-full items-center text-sm font-medium">
              <ThreadTitle threadId={threadId} thread={thread} />
            </div>
            <div className="flex gap-4">
              <ArtifactTrigger />
              <KnowledgeMapTrigger />
            </div>
          </header>
          <main className="flex min-h-0 max-w-full grow flex-col">
            <div className="flex size-full justify-center">
              <MessageList
                className={cn("size-full", !isNewThread && "pt-10")}
                threadId={threadId}
                thread={thread}
              />
            </div>
            <div className="absolute right-0 bottom-0 left-0 z-30 flex justify-center px-4">
              <div
                className={cn(
                  "relative w-full",
                  isNewThread && "-translate-y-[calc(50vh-96px)]",
                  isNewThread
                    ? "max-w-(--container-width-sm)"
                    : "max-w-(--container-width-md)",
                )}
              >
                <div className="absolute -top-4 right-0 left-0 z-0">
                  <div className="absolute right-0 bottom-0 left-0">
                    <TodoList
                      className="bg-background/5"
                      todos={thread.values.todos ?? []}
                      hidden={
                        !thread.values.todos || thread.values.todos.length === 0
                      }
                    />
                  </div>
                </div>
                <InputBox
                  className={cn("bg-background/5 w-full -translate-y-4")}
                  isNewThread={isNewThread}
                  threadId={threadId}
                  autoFocus={isNewThread}
                  status={thread.isLoading ? "streaming" : "ready"}
                  context={settings.context}
                  extraHeader={
                    isNewThread && <Welcome mode={settings.context.mode} />
                  }
                  disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
                  onContextChange={(context) => setSettings("context", context)}
                  onSubmit={handleSubmit}
                  onStop={handleStop}
                />
                {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" && (
                  <div className="text-muted-foreground/67 w-full translate-y-12 text-center text-xs">
                    {t.common.notAvailableInDemoMode}
                  </div>
                )}
              </div>
            </div>
          </main>
        </div>
      </ChatBox>
      </GGLProvider>
    </ThreadContext.Provider>
  );
}

export default function ChatPage() {
  const { threadId, isNewThread, isMock } = useThreadChat();
  const [agentVariant, setAgentVariant] = useState<string | null>(null);

  useEffect(() => {
    if (!threadId || isNewThread) {
      setAgentVariant(null);
      return;
    }
    fetchThreadInfo(threadId)
      .then((info) => setAgentVariant(info.agent_variant))
      .catch(() => setAgentVariant(null));
  }, [threadId, isNewThread]);

  useSpecificChatMode();

  if (!threadId) return null;

  return (
    <ChatContentWithThread
      threadId={threadId}
      isNewThread={isNewThread}
      isMock={isMock}
      agentVariant={agentVariant}
    />
  );
}
