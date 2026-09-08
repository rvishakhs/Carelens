import { CloudOff } from "lucide-react";

import { useSyncQueueStore } from "@/store/syncQueueStore";

export function SyncStatusBadge() {
  const pendingCount = useSyncQueueStore((s) => s.pendingCount);
  const isSyncing = useSyncQueueStore((s) => s.isSyncing);
  const retryNow = useSyncQueueStore((s) => s.retryNow);

  if (pendingCount === 0) return null;

  return (
    <button
      onClick={() => void retryNow()}
      disabled={isSyncing}
      title={`${pendingCount} care ${pendingCount === 1 ? "entry" : "entries"} saved offline -- click to retry sync now`}
      className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm hover:bg-slate-50 disabled:cursor-wait"
    >
      <CloudOff className={`h-5 w-5 text-amber-500 ${isSyncing ? "animate-pulse" : ""}`} />
      <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-[10px] font-semibold text-white">
        {pendingCount}
      </span>
    </button>
  );
}
