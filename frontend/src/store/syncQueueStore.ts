import { create } from "zustand";

import { getPendingCount, syncPending } from "@/lib/careEventQueue";

interface SyncQueueState {
  pendingCount: number;
  isSyncing: boolean;

  /** Re-reads the pending count from localStorage without attempting a sync --
   * call after enqueueing a new item. */
  refresh: () => void;
  /** Attempts to drain the queue against the server, then refreshes the count. */
  retryNow: () => Promise<void>;
}

export const useSyncQueueStore = create<SyncQueueState>((set, get) => ({
  pendingCount: getPendingCount(),
  isSyncing: false,

  refresh: () => set({ pendingCount: getPendingCount() }),

  retryNow: async () => {
    if (get().isSyncing) return;
    set({ isSyncing: true });
    try {
      await syncPending();
    } finally {
      set({ isSyncing: false, pendingCount: getPendingCount() });
    }
  },
}));
