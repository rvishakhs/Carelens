import { AlertTriangle, ArrowLeft, Cookie, HeartPulse } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader } from "@/components/ui/Card";
import { GoalStatusPill, StatusPill } from "@/components/ui/Pill";
import { Tabs } from "@/components/ui/Tabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { CARE_PLAN_GOALS, CARE_RECORDS, KEY_METRICS, RESIDENTS, RESIDENT_ACTIVITY } from "@/lib/mockData";

const TABS = ["Overview", "Care Records", "Care Plan", "Activity"];

export function ResidentDetailPage() {
  const { id } = useParams();
  const [tab, setTab] = useState("Overview");
  const resident = RESIDENTS.find((r) => r.id === id);

  if (!resident) {
    return <Navigate to="/residents" replace />;
  }

  const entries = CARE_RECORDS.flatMap((day) => day.entries).filter((e) => e.residentId === resident.id);

  return (
    <div>
      <Link to="/residents" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" />
        Back to residents
      </Link>

      <PageHeader
        title={resident.name}
        subtitle={`${resident.room} · ${resident.unit} · Primary nurse ${resident.primaryNurse ?? "Unassigned"}`}
      />

      <Card className="mb-5">
        <div className="flex flex-wrap items-center gap-6">
          <Avatar initials={resident.initials} colorClass={resident.avatarColor} size="lg" />
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Age / DOB</p>
            <p className="text-sm font-medium text-slate-900">{resident.age} yrs · {resident.dob}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Gender</p>
            <p className="text-sm font-medium text-slate-900">{resident.gender}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Care Status</p>
            <StatusPill status={resident.careStatus} className="mt-0.5" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Flags</p>
            <div className="mt-1 flex items-center gap-2 text-slate-500">
              {resident.flags?.dnr && (
                <span title="DNR">
                  <AlertTriangle className="h-4 w-4" />
                </span>
              )}
              {resident.flags?.allergies && (
                <span title="Allergies">
                  <HeartPulse className="h-4 w-4" />
                </span>
              )}
              {resident.flags?.diabetic && (
                <span title="Diabetic">
                  <Cookie className="h-4 w-4" />
                </span>
              )}
              {!resident.flags && <span className="text-sm text-slate-300">None</span>}
            </div>
          </div>
        </div>
      </Card>

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="mb-5" />

      {tab === "Overview" && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {KEY_METRICS.map((metric) => (
            <Card key={metric.label}>
              <p className="text-sm text-slate-500">{metric.label}</p>
              <p className="mt-1 text-xl font-semibold text-slate-900">{metric.value}</p>
              <p className="mt-1 text-xs capitalize text-emerald-600">{metric.status}</p>
            </Card>
          ))}
        </div>
      )}

      {tab === "Care Records" && (
        <Card>
          <CardHeader title="Recent Care Records" subtitle={`${entries.length} entries logged`} />
          <div className="divide-y divide-slate-100">
            {entries.map((entry) => (
              <div key={entry.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">{entry.title}</p>
                  <p className="text-xs text-slate-500">
                    {entry.category} · {entry.staff}
                  </p>
                </div>
                <span className="text-xs text-slate-400">{entry.time}</span>
              </div>
            ))}
            {entries.length === 0 && <p className="py-6 text-center text-sm text-slate-400">No records yet.</p>}
          </div>
        </Card>
      )}

      {tab === "Care Plan" && (
        <div className="space-y-3">
          {CARE_PLAN_GOALS.map((goal) => (
            <Card key={goal.id} className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-900">{goal.title}</p>
                <p className="text-sm text-slate-500">{goal.description}</p>
              </div>
              <GoalStatusPill status={goal.status} />
            </Card>
          ))}
        </div>
      )}

      {tab === "Activity" && (
        <Card>
          <CardHeader title="Today's Activity" />
          <div className="space-y-4">
            {RESIDENT_ACTIVITY.map((item) => (
              <div key={item.id} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-900">{item.title}</p>
                  <p className="text-sm text-slate-500">{item.meta}</p>
                </div>
                <span className="text-xs text-slate-400">{item.time}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
