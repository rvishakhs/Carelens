import { useEffect } from "react";
import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/layout/Sidebar";
import { useSyncQueueStore } from "@/store/syncQueueStore";

export function AppLayout() {
  const retryNow = useSyncQueueStore((s) => s.retryNow);
  const refresh = useSyncQueueStore((s) => s.refresh);
  const pendingCount = useSyncQueueStore((s) => s.pendingCount);

  // Sync triggers for the offline-durable care event queue: once on mount (in case
  // entries were queued in a previous session), immediately when the browser regains
  // connectivity, and on a short interval as a fallback for cases the 'online' event
  // doesn't fire (e.g. Wi-Fi connected but the backend itself was down/restarting).
  useEffect(() => {
    refresh();
    void retryNow();

    window.addEventListener("online", retryNow);
    return () => window.removeEventListener("online", retryNow);
  }, [retryNow, refresh]);

  useEffect(() => {
    if (pendingCount === 0) return;
    const interval = setInterval(() => void retryNow(), 20_000);
    return () => clearInterval(interval);
  }, [pendingCount, retryNow]);

  return (
    <div className="flex h-screen overflow-hidden bg-[#f4f6f6]">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1600px] px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
