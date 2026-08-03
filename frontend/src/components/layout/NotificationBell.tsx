import { Bell } from "lucide-react";

export function NotificationBell({ count = 2 }: { count?: number }) {
  return (
    <button className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm hover:bg-slate-50">
      <Bell className="h-5 w-5 text-slate-500" />
      {count > 0 && (
        <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-rose-500 text-[10px] font-semibold text-white">
          {count}
        </span>
      )}
    </button>
  );
}
