import { AlertTriangle, Cookie, HeartPulse, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { GoalStatusPill, StatusPill } from "@/components/ui/Pill";
import { Tabs } from "@/components/ui/Tabs";
import { PageHeader } from "@/components/layout/PageHeader";
import type { ActivityEntry, CarePlan, CareRecordEntry, Resident, ResidentOverview } from "@/types";
import {
  avatarColorFor,
  calculateAge,
  fetchResidentActivity,
  fetchResidentCarePlan,
  fetchResidentCareRecords,
  fetchResidentOverview,
  fetchResidents,
  formatDomainLabel,
  initialsFor,
} from "@/utils/helper";

const TABS = ["Overview", "Care Records", "Care Plan", "Activity"];

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function ResidentDetailPage() {
  const { id } = useParams();
  const [tab, setTab] = useState("Overview");
  const [resident, setResident] = useState<Resident | null>(null);
  const [overview, setOverview] = useState<ResidentOverview | null>(null);
  const [carePlans, setCarePlans] = useState<CarePlan[]>([]);
  const [careRecords, setCareRecords] = useState<CareRecordEntry[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        const [residents, overviewData, carePlanData, careRecordData, activityData] = await Promise.all([
          fetchResidents(),
          fetchResidentOverview(id),
          fetchResidentCarePlan(id),
          fetchResidentCareRecords(id),
          fetchResidentActivity(id),
        ]);
        if (cancelled) return;

        const match = residents.find((r) => r.id === id);
        if (!match) {
          setNotFound(true);
          return;
        }
        setResident(match);
        setOverview(overviewData);
        setCarePlans(carePlanData);
        setCareRecords(careRecordData);
        setActivity(activityData);
      } catch (err) {
        console.error(err);
        setNotFound(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (notFound) {
    return <Navigate to="/residents" replace />;
  }

  if (loading || !resident) {
    return <div className="py-12 text-center text-sm text-slate-400">Loading resident…</div>;
  }

  const displayName = `${resident.preferred_name || resident.first_name} ${resident.last_name}`;

  return (
    <div>
      <Link to="/residents" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-700">
        Back to residents
      </Link>

      <PageHeader
        title={displayName}
        subtitle={`${resident.room_number ?? "No room assigned"} · ${resident.floor_name ?? "No floor assigned"}`}
      />

      <Card className="mb-5">
        <div className="flex flex-wrap items-center gap-6">
          <Avatar initials={initialsFor(resident.first_name, resident.last_name)} colorClass={avatarColorFor(resident.id)} size="lg" />
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Age / DOB</p>
            <p className="text-sm font-medium text-slate-900">
              {calculateAge(resident.date_of_birth)} yrs · {resident.date_of_birth}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Gender</p>
            <p className="text-sm font-medium text-slate-900 capitalize">{resident.gender ?? "Not recorded"}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Status</p>
            <StatusPill status={resident.status} className="mt-0.5" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Flags</p>
            <div className="mt-1 flex items-center gap-2 text-slate-500">
              {resident.dnacpr && (
                <span title="DNACPR">
                  <AlertTriangle className="h-4 w-4" />
                </span>
              )}
              {resident.has_allergies && (
                <span title="Allergies">
                  <HeartPulse className="h-4 w-4" />
                </span>
              )}
              {resident.diabetic && (
                <span title="Diabetic">
                  <Cookie className="h-4 w-4" />
                </span>
              )}
              {!resident.dnacpr && !resident.has_allergies && !resident.diabetic && (
                <span className="text-sm text-slate-300">None</span>
              )}
            </div>
          </div>
        </div>
      </Card>

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="mb-5" />

      {tab === "Overview" && overview && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <p className="text-sm text-slate-500">Mobility level</p>
              <p className="mt-1 text-lg font-semibold capitalize text-slate-900">
                {overview.mobility_level?.replace(/_/g, " ") ?? "Not assessed"}
              </p>
            </Card>
            <Card>
              <p className="text-sm text-slate-500">Falls risk</p>
              <p className="mt-1 text-lg font-semibold capitalize text-slate-900">{overview.falls_risk_level ?? "Not assessed"}</p>
            </Card>
            <Card>
              <p className="text-sm text-slate-500">Skin integrity risk</p>
              <p className="mt-1 text-lg font-semibold capitalize text-slate-900">{overview.skin_risk_level ?? "Not assessed"}</p>
            </Card>
            <Card>
              <p className="text-sm text-slate-500">Active medications</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">{overview.active_medication_count}</p>
            </Card>
          </div>

          {overview.latest_vitals && (
            <Card>
              <CardHeader title="Latest Vital Signs" subtitle={formatDateTime(overview.latest_vitals.recorded_at)} />
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                  <p className="text-xs text-slate-500">Blood pressure</p>
                  <p className="text-sm font-medium text-slate-900">
                    {overview.latest_vitals.blood_pressure_systolic ?? "–"}/{overview.latest_vitals.blood_pressure_diastolic ?? "–"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Heart rate</p>
                  <p className="text-sm font-medium text-slate-900">{overview.latest_vitals.heart_rate_bpm ?? "–"} bpm</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Oxygen sats</p>
                  <p className="text-sm font-medium text-slate-900">{overview.latest_vitals.oxygen_saturation_pct ?? "–"}%</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">NEWS2</p>
                  <p className="text-sm font-medium text-slate-900">{overview.latest_vitals.news2_score ?? "–"}</p>
                </div>
              </div>
            </Card>
          )}

          {overview.weight_trend.length > 0 && (
            <Card>
              <CardHeader title="Weight Trend" subtitle="Most recent recordings" />
              <div className="flex flex-wrap gap-3">
                {overview.weight_trend.map((point) => (
                  <div key={point.recorded_at} className="rounded-lg bg-slate-50 px-3 py-2 text-center">
                    <p className="text-sm font-semibold text-slate-900">{point.weight_kg}kg</p>
                    <p className="text-xs text-slate-500">{formatDateTime(point.recorded_at)}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Diagnoses" subtitle={`${overview.diagnoses.length} recorded`} />
              <div className="space-y-2">
                {overview.diagnoses.map((d) => (
                  <div key={d.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="text-slate-900">
                      {d.condition_name} {d.is_primary && <span className="text-xs text-brand-600">(primary)</span>}
                    </span>
                    <span className="text-xs capitalize text-slate-500">{d.status}</span>
                  </div>
                ))}
                {overview.diagnoses.length === 0 && <p className="text-sm text-slate-400">No diagnoses recorded.</p>}
              </div>
            </Card>

            <Card>
              <CardHeader title="Allergies" subtitle={`${overview.allergies.length} recorded`} />
              <div className="space-y-2">
                {overview.allergies.map((a) => (
                  <div key={a.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="text-slate-900">{a.allergen}</span>
                    <span className="text-xs text-slate-500">
                      {a.reaction} · {a.severity}
                    </span>
                  </div>
                ))}
                {overview.allergies.length === 0 && <p className="text-sm text-slate-400">No known allergies.</p>}
              </div>
            </Card>

            <Card>
              <CardHeader title="Contacts" subtitle={`${overview.contacts.length} recorded`} />
              <div className="space-y-2">
                {overview.contacts.map((c) => (
                  <div key={c.id} className="text-sm">
                    <p className="text-slate-900">
                      {c.full_name}{" "}
                      {c.is_next_of_kin && <span className="text-xs text-brand-600">(next of kin)</span>}
                    </p>
                    <p className="text-xs text-slate-500 capitalize">
                      {c.relationship} · {c.phone ?? c.email ?? "No contact details"}
                    </p>
                  </div>
                ))}
                {overview.contacts.length === 0 && <p className="text-sm text-slate-400">No contacts recorded.</p>}
              </div>
            </Card>

            <Card>
              <CardHeader title="Advance Care Directives" subtitle={`${overview.advance_directives.length} current`} />
              <div className="space-y-2">
                {overview.advance_directives.map((d) => (
                  <div key={d.id} className="text-sm">
                    <p className="font-medium text-slate-900">{d.directive_type}</p>
                    <p className="text-xs text-slate-500">{d.summary}</p>
                  </div>
                ))}
                {overview.advance_directives.length === 0 && <p className="text-sm text-slate-400">None recorded.</p>}
              </div>
            </Card>
          </div>

          {overview.life_history && (
            <Card>
              <CardHeader title="About" subtitle="Life history and personal background" />
              <div className="space-y-2 text-sm text-slate-700">
                <p>{overview.life_history.free_text_narrative}</p>
                {overview.life_history.family_background && <p>{overview.life_history.family_background}</p>}
                {overview.life_history.significant_events && <p>{overview.life_history.significant_events}</p>}
                {overview.life_history.important_relationships && <p>{overview.life_history.important_relationships}</p>}
              </div>
            </Card>
          )}

          {overview.top_preferences.length > 0 && (
            <Card>
              <CardHeader title="Preferences" subtitle="What matters to this resident" />
              <div className="flex flex-wrap gap-2">
                {overview.top_preferences.map((p) => (
                  <span
                    key={p.preference}
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      p.is_like ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                    }`}
                  >
                    {p.preference}
                  </span>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {tab === "Care Records" && (
        <Card>
          <CardHeader
            title="Recent Care Records"
            subtitle={`${careRecords.length} entries logged`}
            action={
              <Link to={`/residents/${id}/care-records`}>
                <Button>
                  <Plus className="h-4 w-4" />
                  Record Care
                </Button>
              </Link>
            }
          />
          <div className="divide-y divide-slate-100">
            {careRecords.map((entry) => (
              <div key={entry.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">{entry.title}</p>
                  {entry.detail && <p className="text-xs text-slate-500">{entry.detail}</p>}
                </div>
                <span className="text-xs text-slate-400">{formatDateTime(entry.recorded_at)}</span>
              </div>
            ))}
            {careRecords.length === 0 && <p className="py-6 text-center text-sm text-slate-400">No records yet.</p>}
          </div>
        </Card>
      )}

      {tab === "Care Plan" && (
        <div className="space-y-3">
          {carePlans.map((plan) => (
            <Card key={plan.id}>
              <CardHeader title={formatDomainLabel(plan.domain)} subtitle={plan.goal} />
              <div className="space-y-2">
                {plan.goals.map((goal) => (
                  <div key={goal.id} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{goal.goal_text}</p>
                      {goal.target && <p className="truncate text-xs text-slate-500">Target: {goal.target}</p>}
                    </div>
                    <GoalStatusPill status={goal.status} className="shrink-0" />
                  </div>
                ))}
              </div>
            </Card>
          ))}
          {carePlans.length === 0 && <p className="py-6 text-center text-sm text-slate-400">No active care plans.</p>}
        </div>
      )}

      {tab === "Activity" && (
        <Card>
          <CardHeader title="Recent Activity" />
          <div className="space-y-4">
            {activity.map((item) => (
              <div key={item.id} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-900">{item.title}</p>
                  {item.detail && <p className="text-sm text-slate-500">{item.detail}</p>}
                </div>
                <span className="text-xs text-slate-400">{formatDateTime(item.occurred_at)}</span>
              </div>
            ))}
            {activity.length === 0 && <p className="py-6 text-center text-sm text-slate-400">No activity recorded.</p>}
          </div>
        </Card>
      )}
    </div>
  );
}
