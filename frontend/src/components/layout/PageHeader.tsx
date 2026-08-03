import type { ReactNode } from "react";

import { CareHomeSelector } from "@/components/layout/CareHomeSelector";
import { NotificationBell } from "@/components/layout/NotificationBell";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        {actions}
        <CareHomeSelector />
        <NotificationBell />
      </div>
    </div>
  );
}
