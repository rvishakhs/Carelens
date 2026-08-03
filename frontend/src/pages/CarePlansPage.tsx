import { useNavigate } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader } from "@/components/ui/Card";
import { GoalStatusPill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import { CARE_PLAN_GOALS, RESIDENTS } from "@/lib/mockData";

export function CarePlansPage() {
  const navigate = useNavigate();

  return (
    <div>
      <PageHeader title="Care Plans" subtitle="Active goals and progress for every resident" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {RESIDENTS.map((resident) => (
          <Card key={resident.id} className="cursor-pointer hover:shadow-md" onClick={() => navigate(`/residents/${resident.id}`)}>
            <CardHeader
              title={resident.name}
              subtitle={`${resident.room} · ${resident.unit}`}
              action={<Avatar initials={resident.initials} colorClass={resident.avatarColor} size="sm" />}
            />
            <div className="space-y-2.5">
              {CARE_PLAN_GOALS.map((goal) => (
                <div key={goal.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">{goal.title}</p>
                    <p className="truncate text-xs text-slate-500">{goal.description}</p>
                  </div>
                  <GoalStatusPill status={goal.status} className="shrink-0" />
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
