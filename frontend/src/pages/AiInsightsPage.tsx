import { CheckCircle2, Sparkles } from "lucide-react";

import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader } from "@/components/ui/Card";
import { PageHeader } from "@/components/layout/PageHeader";
import { AI_CHECKLIST, AI_RECOMMENDATIONS, ATTENTION_RESIDENTS, KEY_METRICS } from "@/lib/mockData";

export function AiInsightsPage() {
  return (
    <div>
      <PageHeader title="AI Insights" subtitle="Automated observations generated from today's care records" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {KEY_METRICS.map((metric) => (
          <Card key={metric.label}>
            <p className="text-sm text-slate-500">{metric.label}</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{metric.value}</p>
            <p className="mt-1 text-xs capitalize text-emerald-600">{metric.status}</p>
          </Card>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Recommendations" subtitle="Suggested next actions for care staff" />
          <div className="space-y-3">
            {AI_RECOMMENDATIONS.map((rec) => (
              <div key={rec} className="flex items-start gap-3 rounded-lg bg-brand-50 p-3">
                <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                <p className="text-sm text-slate-700">{rec}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Daily Checklist" subtitle="Auto-generated summary of today" />
          <div className="space-y-3">
            {AI_CHECKLIST.map((item) => (
              <div key={item} className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                <p className="text-sm text-slate-700">{item}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Residents Requiring Attention" subtitle="Flagged by anomaly detection" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ATTENTION_RESIDENTS.map((resident) => (
            <div key={resident.id} className="flex items-center gap-3 rounded-xl border border-amber-100 bg-amber-50/60 p-3">
              <Avatar initials={resident.name.split(" ").map((p) => p[0]).join("")} colorClass="bg-amber-200 text-amber-900" size="sm" />
              <div className="min-w-0">
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
  );
}
