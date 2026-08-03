import { ClipboardList, Pill, Sparkles, UsersRound, Users as UsersIcon } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  ATTENTION_RESIDENTS,
  CARE_OVERVIEW_BREAKDOWN,
  DASHBOARD_STATS,
  RECENT_ACTIVITY,
  RESIDENTS,
} from "@/lib/mockData";

function initialsFor(name: string) {
  const resident = RESIDENTS.find((r) => r.name === name);
  return resident?.initials ?? name.slice(0, 2).toUpperCase();
}

export function DashboardPage() {
  const total = CARE_OVERVIEW_BREAKDOWN.reduce((sum, d) => sum + d.value, 0);

  return (
    <div>
      <PageHeader title="Good morning, Sarah" subtitle="Tuesday, 9 July 2024 · Overview across your care home" />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard icon={UsersIcon} label="Residents" value={DASHBOARD_STATS.residents.value} delta={DASHBOARD_STATS.residents.delta} tone="positive" />
        <StatCard icon={ClipboardList} label="Care Records" value={DASHBOARD_STATS.careRecords.value} delta={DASHBOARD_STATS.careRecords.delta} />
        <StatCard icon={Sparkles} label="AI Alerts" value={DASHBOARD_STATS.aiAlerts.value} delta={DASHBOARD_STATS.aiAlerts.delta} tone="warning" />
        <StatCard icon={Pill} label="Medications" value={DASHBOARD_STATS.medications.value} delta={DASHBOARD_STATS.medications.delta} />
        <StatCard icon={UsersRound} label="Staff on Duty" value={DASHBOARD_STATS.staffOnDuty.value} delta={DASHBOARD_STATS.staffOnDuty.delta} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader title="Care Overview" subtitle="Breakdown of today's recorded care activity" />
            <div className="flex flex-col items-center gap-6 sm:flex-row">
              <div className="h-48 w-48 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={CARE_OVERVIEW_BREAKDOWN}
                      dataKey="value"
                      nameKey="label"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={2}
                      strokeWidth={2}
                      stroke="#ffffff"
                    >
                      {CARE_OVERVIEW_BREAKDOWN.map((entry) => (
                        <Cell key={entry.label} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value) => [`${value}%`, ""]}
                      contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 13 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-2.5">
                {CARE_OVERVIEW_BREAKDOWN.map((entry) => (
                  <div key={entry.label} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                      <span className="text-slate-600">{entry.label}</span>
                    </div>
                    <span className="font-medium text-slate-900">{Math.round((entry.value / total) * 100)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Recent Activity" subtitle="Latest updates logged by your team" />
            <div className="space-y-4">
              {RECENT_ACTIVITY.map((item) => (
                <div key={item.id} className="flex items-start gap-3">
                  <Avatar initials={initialsFor(item.title)} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900">{item.title}</p>
                    <p className="text-sm text-slate-500">{item.meta}</p>
                  </div>
                  <span className="shrink-0 text-xs text-slate-400">{item.time}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <Card>
          <CardHeader title="Residents Requiring Attention" subtitle={`${ATTENTION_RESIDENTS.length} flagged today`} />
          <div className="space-y-3">
            {ATTENTION_RESIDENTS.map((resident) => (
              <div key={resident.id} className="flex items-center gap-3 rounded-xl border border-amber-100 bg-amber-50/60 p-3">
                <Avatar initials={initialsFor(resident.name)} colorClass="bg-amber-200 text-amber-900" size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900">{resident.name}</p>
                  <p className="truncate text-xs text-slate-500">
                    {resident.room} · {resident.issue}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
