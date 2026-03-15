"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

export type RightPanelView = "artifacts" | "ggl" | null;

export interface RightPanelContextType {
  view: RightPanelView;
  setView: (view: RightPanelView) => void;
  gglEnabled: boolean;
  openArtifacts: () => void;
  openGGL: () => void;
  close: () => void;
}

const RightPanelContext = createContext<RightPanelContextType | undefined>(
  undefined,
);

interface RightPanelProviderProps {
  children: ReactNode;
  gglEnabled?: boolean;
}

export function RightPanelProvider({
  children,
  gglEnabled = false,
}: RightPanelProviderProps) {
  const [view, setView] = useState<RightPanelView>(null);

  const openArtifacts = useCallback(() => setView("artifacts"), []);
  const openGGL = useCallback(() => setView("ggl"), []);
  const close = useCallback(() => setView(null), []);

  const value: RightPanelContextType = {
    view,
    setView,
    gglEnabled,
    openArtifacts,
    openGGL,
    close,
  };

  return (
    <RightPanelContext.Provider value={value}>
      {children}
    </RightPanelContext.Provider>
  );
}

export function useRightPanel() {
  const context = useContext(RightPanelContext);
  return context;
}
