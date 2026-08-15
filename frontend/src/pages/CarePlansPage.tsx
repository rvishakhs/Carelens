import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader } from "@/components/ui/Card";
import { GoalStatusPill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import type { CarePlan, Resident } from "@/types";
import { avatarColorFor, fetchAllCarePlans, fetchResidents, formatDomainLabel, initialsFor } from "@/utils/helper";

export function CarePlansPage() {
  const navigate = useNavigate();
  const [residents, setResidents] = useState<Resident[]>([]);
  const [carePlans, setCarePlans] = useState<CarePlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchResidents(), fetchAllCarePlans()])
      .then(([r, c]) => {
        setResidents(r);
        setCarePlans(c);
      })
      .catch((err) => {
        console.error(err);
        setError("Unable to load care plans");
      })
      .finally(() => setLoading(false));
  }, []);

  const plansByResident = new Map<string, CarePlan[]>();
  for (const plan of carePlans) {
    const existing = plansByResident.get(plan.resident_id) ?? [];
    existing.push(plan);
    plansByResident.set(plan.resident_id, existing);
  }

  return (
    <div>
      <PageHeader title="Care Plans" subtitle="Active goals and progress for every resident" />

      {error && <div className="mb-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
      {loading && <p className="py-12 text-center text-sm text-slate-400">Loading care plans…</p>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {!loading &&
          residents
            .filter((resident) => (plansByResident.get(resident.id) ?? []).length > 0)
            .map((resident) => {
              const plans = plansByResident.get(resident.id) ?? [];
              const displayName = `${resident.preferred_name || resident.first_name} ${resident.last_name}`;
              return (
                <Card key={resident.id} className="cursor-pointer hover:shadow-md" onClick={() => navigate(`/residents/${resident.id}`)}>
                  <CardHeader
                    title={displayName}
                    subtitle={`${resident.room_number ?? "No room"} · ${resident.floor_name ?? "No floor"}`}
                    action={<Avatar initials={initialsFor(resident.first_name, resident.last_name)} colorClass={avatarColorFor(resident.id)} size="sm" />}
                  />
                  <div className="space-y-2.5">
                    {plans.flatMap((plan) =>
                      plan.goals.map((goal) => (
                        <div key={goal.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2.5">
                          <div className="min-w-0">
                            <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-400">
                              {formatDomainLabel(plan.domain)}
                            </p>
                            <p className="truncate text-sm font-medium text-slate-900">{goal.goal_text}</p>
                          </div>
                          <GoalStatusPill status={goal.status} className="shrink-0" />
                        </div>
                      )),
                    )}
                  </div>
                </Card>
              );
            })}

        {!loading && residents.every((r) => (plansByResident.get(r.id) ?? []).length === 0) && (
          <p className="col-span-full py-12 text-center text-sm text-slate-400">No active care plans.</p>
        )}
      </div>
    </div>
  );
}
