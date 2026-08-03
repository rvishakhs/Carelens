import { create } from "zustand";

import { CARE_HOMES } from "@/lib/mockData";

interface UiState {
  selectedCareHome: string;
  setSelectedCareHome: (name: string) => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  closeSidebar: () => void;
}

/** UI-only state: which care home is selected, mobile sidebar open/closed. */
export const useUiStore = create<UiState>((set) => ({
  selectedCareHome: CARE_HOMES[0],
  setSelectedCareHome: (name) => set({ selectedCareHome: name }),
  sidebarOpen: false,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  closeSidebar: () => set({ sidebarOpen: false }),
}));
