import { clsx } from "clsx";
import type { ReactNode } from "react";

import type { CareStatus, GoalStatus } from "@/types";

type Tone = "rose" | "amber" | "emerald" | "slate" | "indigo" | "sky";

const toneStyles: Record<Tone, string> = {
  rose: "bg-rose-100 text-rose-700",
  amber: "bg-amber-100 text-amber-700",
  emerald: "bg-emerald-100 text-emerald-700",
  slate: "bg-slate-100 text-slate-600",
  indigo: "bg-indigo-100 text-indigo-700",
  sky: "bg-sky-100 text-sky-700",
};

export function Pill({
  tone = "slate",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium", toneStyles[tone], className)}>
      {children}
    </span>
  );
}

const careStatusTone: Record<CareStatus, Tone> = {
  good: "emerald",
  attention: "amber",
  high_risk: "rose",
};

const careStatusLabel: Record<CareStatus, string> = {
  good: "Good",
  attention: "Attention",
  high_risk: "High Risk",
};

export function StatusPill({ status, className }: { status: CareStatus; className?: string }) {
  return (
    <Pill tone={careStatusTone[status]} className={className}>
      {careStatusLabel[status]}
    </Pill>
  );
}

const goalStatusTone: Record<GoalStatus, Tone> = {
  on_track: "emerald",
  at_risk: "amber",
  off_track: "rose",
};

const goalStatusLabel: Record<GoalStatus, string> = {
  on_track: "On Track",
  at_risk: "At Risk",
  off_track: "Off Track",
};

export function GoalStatusPill({ status, className }: { status: GoalStatus; className?: string }) {
  return (
    <Pill tone={goalStatusTone[status]} className={className}>
      {goalStatusLabel[status]}
    </Pill>
  );
}
