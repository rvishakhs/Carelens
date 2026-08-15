import { clsx } from "clsx";
import type { ReactNode } from "react";

import type { GoalStatus, ResidentStatus } from "@/types";

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

const residentStatusTone: Record<ResidentStatus, Tone> = {
  active: "emerald",
  hospitalized: "amber",
  discharged: "slate",
  archived: "slate",
};

const residentStatusLabel: Record<ResidentStatus, string> = {
  active: "Active",
  hospitalized: "Hospitalized",
  discharged: "Discharged",
  archived: "Archived",
};

export function StatusPill({ status, className }: { status: ResidentStatus; className?: string }) {
  return (
    <Pill tone={residentStatusTone[status]} className={className}>
      {residentStatusLabel[status]}
    </Pill>
  );
}

// Mirrors care_plan_goals.status (migration 0020's care_plan_goal_status enum).
const goalStatusTone: Record<GoalStatus, Tone> = {
  not_started: "slate",
  in_progress: "sky",
  improving: "emerald",
  maintained: "emerald",
  declining: "amber",
  achieved: "indigo",
  discontinued: "slate",
};

const goalStatusLabel: Record<GoalStatus, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  improving: "Improving",
  maintained: "Maintained",
  declining: "Declining",
  achieved: "Achieved",
  discontinued: "Discontinued",
};

export function GoalStatusPill({ status, className }: { status: GoalStatus; className?: string }) {
  return (
    <Pill tone={goalStatusTone[status]} className={className}>
      {goalStatusLabel[status]}
    </Pill>
  );
}
