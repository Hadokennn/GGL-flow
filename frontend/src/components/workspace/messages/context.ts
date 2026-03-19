import type { BaseStream } from "@langchain/langgraph-sdk/react";
import type { RefObject } from "react";
import { createContext, useContext } from "react";

import type { AgentThreadState } from "@/core/threads";

/** Checkpoint for submit (Omit<Checkpoint, "thread_id">) */
export type PendingCheckpoint = {
  checkpoint_ns: string;
  checkpoint_id: string;
  checkpoint_map: Record<string, unknown> | null;
};

export interface ThreadContextType {
  thread: BaseStream<AgentThreadState>;
  isMock?: boolean;
  /** Ref for checkpoint from setActiveNode; sendMessage reads and clears before submit */
  pendingCheckpointRef?: RefObject<PendingCheckpoint | null>;
}

export const ThreadContext = createContext<ThreadContextType | undefined>(
  undefined,
);

export function useThread() {
  const context = useContext(ThreadContext);
  if (context === undefined) {
    throw new Error("useThread must be used within a ThreadContext");
  }
  return context;
}
