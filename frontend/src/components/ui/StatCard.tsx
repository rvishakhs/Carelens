import { clsx } from "clsx";
import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/Card";

export function StatCard({
  icon: Icon,
  label,
  value,
  delta,
  tone = "default",
  className,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  delta?: string;
  tone?: "default" | "warning" | "positive";
  className?: string;
}) {
  return (
    <Card className={clsx("flex-1", className)}>
      <div className="flex items-center gap-2 text-slate-500">
        <Icon className="h-4 w-4" />
        <span className="text-sm">{label}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
      {delta && (
        <div
          className={clsx(
            "mt-1 text-xs font-medium",
            tone === "warning" && "text-rose-600",
            tone === "positive" && "text-emerald-600",
            tone === "default" && "text-slate-400",
          )}
        >
          {delta}
        </div>
      )}
    </Card>
  );
}
