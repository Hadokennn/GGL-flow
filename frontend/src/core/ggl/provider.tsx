import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { fetchGGLGraph } from "./api";
import type { GGLState } from "./types";

interface GGLContextValue {
  gglState: GGLState | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  isEnabled: boolean;
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

  const value: GGLContextValue = {
    gglState,
    isLoading,
    error,
    refetch,
    isEnabled: enabled && !!threadId,
  };

  return <GGLContext.Provider value={value}>{children}</GGLContext.Provider>;
}

export function useGGL(): GGLContextValue {
  const context = useContext(GGLContext);
  if (!context) {
    throw new Error("useGGL must be used within GGLProvider");
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
