import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { fetchGGLGraph } from "./api";
import type { GGLState } from "./types";

interface GGLContextValue {
  gglState: GGLState | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  isEnabled: boolean;
  highlightedNodeId: string | null;
  setHighlightedNodeId: (nodeId: string | null) => void;
  scrollToMessage: (messageId: string) => void;
  registerMessageScrollHandler: (handler: (messageId: string) => void) => () => void;
}

const GGLContext = createContext<GGLContextValue | null>(null);

interface GGLProviderProps {
  threadId: string | null;
  children: React.ReactNode;
  enabled?: boolean;
  streamedState?: GGLState | null;
}

export function GGLProvider({
  threadId,
  children,
  enabled = false,
  streamedState = null,
}: GGLProviderProps) {
  const [gglState, setGglState] = useState<GGLState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [highlightedNodeId, setHighlightedNodeId] = useState<string | null>(null);
  const [messageScrollHandlers, setMessageScrollHandlers] = useState<Array<(messageId: string) => void>>([]);

  const refetch = useCallback(async () => {
    if (!enabled || !threadId) {
      setGglState(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await fetchGGLGraph(threadId);
      setGglState(data);
    } catch (e) {
      setError(e as Error);
    } finally {
      setIsLoading(false);
    }
  }, [enabled, threadId]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    if (!streamedState) {
      return;
    }
    setGglState(streamedState);
    setError(null);
  }, [enabled, streamedState]);

  const scrollToMessage = useCallback((messageId: string) => {
    messageScrollHandlers.forEach(handler => handler(messageId));
  }, [messageScrollHandlers]);

  const registerMessageScrollHandler = useCallback((handler: (messageId: string) => void) => {
    setMessageScrollHandlers(prev => [...prev, handler]);
    return () => {
      setMessageScrollHandlers(prev => prev.filter(h => h !== handler));
    };
  }, []);

  const value: GGLContextValue = {
    gglState,
    isLoading,
    error,
    refetch,
    isEnabled: enabled && !!threadId,
    highlightedNodeId,
    setHighlightedNodeId,
    scrollToMessage,
    registerMessageScrollHandler,
  };

  return <GGLContext.Provider value={value}>{children}</GGLContext.Provider>;
}

export function useGGL(): GGLContextValue {
  const context = useContext(GGLContext);
  if (!context) {
    // 提供默认值以支持非 GGL 模式
    return {
      gglState: null,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      refetch: async () => {},
      isEnabled: false,
      highlightedNodeId: null,
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      setHighlightedNodeId: () => {},
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      scrollToMessage: () => {},
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      registerMessageScrollHandler: () => () => {},
    };
  }
  return context;
}

export function useIsGGLEnabled(): boolean {
  const { isEnabled } = useGGL();
  return isEnabled;
}

export function useGGLState(): GGLState | null {
  const { gglState, isEnabled } = useGGL();
  return isEnabled ? gglState : null;
}
