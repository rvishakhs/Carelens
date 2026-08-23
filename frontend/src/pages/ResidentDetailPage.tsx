import { clsx } from "clsx";
import { Accessibility, ChevronRight, Edit, MoreHorizontal, Pill as PillIcon, Plus, Shield, TriangleAlert, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { GoalStatusPill, Pill, StatusPill } from "@/components/ui/Pill";
import { TileGrid } from "@/components/ui/Tile";
import { Tabs } from "@/components/ui/Tabs";
import type { ActivityEntry, CareEventHistoryItem, CareEventStatus, CarePlan, Resident, ResidentOverview } from "@/types";
import {
  avatarColorFor,
  calculateAge,
  fetchResidentActivity,
  fetchResidentCareEvents,
  fetchResidentCarePlan,
  fetchResidentOverview,
  fetchResidents,
  formatDomainLabel,
  initialsFor,
} from "@/utils/helper";

const TABS = ["Overview", "Care Records", "Care Plan", "Activity"];

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Green/amber/rose dot from a risk-level string; no clinical scoring implied beyond
 * the level text the backend already returned (mobility_level, falls_risk_level, ...). */
function riskDotClass(value: string | null | undefined): string {
  if (!value) return "bg-slate-300";
  const v = value.toLowerCase();
  if (v.includes("high")) return "bg-rose-500";
  if (v.includes("moderate") || v.includes("medium")) return "bg-amber-500";
  return "bg-emerald-500";
}

function GlanceRow({ icon: Icon, label, value, tone }: { icon: LucideIcon; label: string; value: string; tone: string }) {
  return (
    <div className="flex items-center gap-3 py-2.5 text-sm">
      <span className={`h-2 w-2 shrink-0 rounded-full ${tone}`} />
      <Icon className="h-4 w-4 shrink-0 text-slate-400" />
      <span className="flex-1 text-slate-600">{label}</span>
      <span className="font-medium capitalize text-slate-900">{value}</span>
    </div>
  );
}

function VitalTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2.5">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

/** Green outline/dot for a completed entry, yellow for declined, red for
 * refused/not applicable (i.e. not done) -- per the resident's Care Records tile
 * view. Tiles only show the dot; the label still backs the detail modal's badge. */
function statusTone(status: CareEventStatus): { border: string; dot: string; badge: string; label: string } {
  switch (status) {
    case "completed":
      return { border: "border-emerald-300", dot: "bg-emerald-500", badge: "bg-emerald-100 text-emerald-700", label: "Completed" };
    case "declined":
      return { border: "border-amber-300", dot: "bg-amber-500", badge: "bg-amber-100 text-amber-700", label: "Declined" };
    case "refused":
      return { border: "border-rose-300", dot: "bg-rose-500", badge: "bg-rose-100 text-rose-700", label: "Refused" };
    case "not_applicable":
      return { border: "border-rose-300", dot: "bg-rose-500", badge: "bg-rose-100 text-rose-700", label: "Not Applicable" };
  }
}

export function ResidentDetailPage() {
  const { id } = useParams();
  const [tab, setTab] = useState("Overview");
  const [resident, setResident] = useState<Resident | null>(null);
  const [overview, setOverview] = useState<ResidentOverview | null>(null);
  const [carePlans, setCarePlans] = useState<CarePlan[]>([]);
  const [careEvents, setCareEvents] = useState<CareEventHistoryItem[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<CareEventHistoryItem | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        const [residents, overviewData, carePlanData, careEventData, activityData] = await Promise.all([
          fetchResidents(),
          fetchResidentOverview(id),
          fetchResidentCarePlan(id),
          fetchResidentCareEvents(id),
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
        setCareEvents(careEventData);
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

  const allGoals = useMemo(() => carePlans.flatMap((plan) => plan.goals.map((goal) => ({ ...goal, domain: plan.domain }))), [carePlans]);

  if (notFound) {
    return <Navigate to="/residents" replace />;
  }

  if (loading || !resident) {
    return <div className="py-12 text-center text-sm text-slate-400">Loading resident…</div>;
  }

  const displayName = `${resident.preferred_name || resident.first_name} ${resident.last_name}`;

  return (
    <div>
      <div className="mb-4 flex items-center gap-1.5 text-sm text-slate-500">
        <Link to="/residents" className="font-medium hover:text-slate-700">
          Residents
        </Link>
        <span>/</span>
        <span className="text-slate-700">{displayName}</span>
      </div>

      <div className="mb-6 px-1">
  <div className="flex flex-wrap items-center justify-between gap-6">

    {/* Resident Profile */}
    <div className="flex items-center gap-5">
      <Avatar
        initials={initialsFor(resident.first_name, resident.last_name)}
        photoUrl={resident.photo_url}
        colorClass={avatarColorFor(resident.id)}
        size="xl"

      />

      <div className="min-w-0">
        <h2 className="text-2xl font-semibold text-slate-900">
          {displayName}
        </h2>

        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-500">
          <span>{resident.room_number ?? "No room assigned"}</span>
          <span>·</span>

          <span>
            Age {calculateAge(resident.date_of_birth)}
          </span>

          {resident.gender && (
            <>
              <span>·</span>
              <span className="capitalize">{resident.gender}</span>
            </>
          )}

          <StatusPill
            status={resident.status}
            className="ml-1"
          />
        </div>

        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {resident.has_allergies ? (
            <Pill tone="amber">
              Allergies
              {overview?.allergies.length
                ? `: ${overview.allergies
                    .map((a) => a.allergen)
                    .join(", ")}`
                : ""}
            </Pill>
          ) : (
            <Pill tone="slate">No known allergies</Pill>
          )}

          {resident.dnacpr ? (
            <Pill tone="rose">DNACPR</Pill>
          ) : (
            <Pill tone="slate">No DNACPR</Pill>
          )}
        </div>
      </div>
    </div>

    {/* Actions + Primary Nurse */}
    <div className="flex flex-col items-stretch gap-3">

      <div className="flex gap-2">
        <Button variant="secondary" className="flex-1">
          <Edit className="mr-2 h-4 w-4" />
          Edit Profile
        </Button>

        <Button variant="secondary">
          More
          <MoreHorizontal className="ml-2 h-4 w-4" />
        </Button>
      </div>

      {/* Primary Nurse */}
      <div className="w-60 rounded-xl bg-slate-50/70 p-3">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
          Primary Nurse
        </p>

        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-400">
            <UserRound className="h-5 w-5" />
          </div>

          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-900">
              Sarah Johnson
            </p>
            <p className="text-xs text-slate-400">
              Senior Nurse
            </p>
          </div>
        </div>
      </div>
    </div>

  </div>
</div>

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="mb-5" />

      {tab === "Overview" && overview && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader title="At a Glance" />
              <div className="divide-y divide-slate-100">
                <GlanceRow
                  icon={Accessibility}
                  label="Mobility"
                  value={overview.mobility_level?.replace(/_/g, " ") ?? "Not assessed"}
                  tone="bg-slate-300"
                />
                <GlanceRow
                  icon={TriangleAlert}
                  label="Falls risk"
                  value={overview.falls_risk_level ?? "Not assessed"}
                  tone={riskDotClass(overview.falls_risk_level)}
                />
                <GlanceRow
                  icon={Shield}
                  label="Skin integrity risk"
                  value={overview.skin_risk_level ?? "Not assessed"}
                  tone={riskDotClass(overview.skin_risk_level)}
                />
                <GlanceRow icon={PillIcon} label="Active medications" value={String(overview.active_medication_count)} tone="bg-sky-500" />
              </div>
            </Card>

            <Card>
              <CardHeader title="Vitals" subtitle={overview.latest_vitals ? formatDateTime(overview.latest_vitals.recorded_at) : undefined} />
              {overview.latest_vitals ? (
                <div className="grid grid-cols-2 gap-3">
                  <VitalTile
                    label="Blood pressure"
                    value={`${overview.latest_vitals.blood_pressure_systolic ?? "–"}/${overview.latest_vitals.blood_pressure_diastolic ?? "–"}`}
                  />
                  <VitalTile label="Heart rate" value={`${overview.latest_vitals.heart_rate_bpm ?? "–"} bpm`} />
                  <VitalTile label="Oxygen sats" value={`${overview.latest_vitals.oxygen_saturation_pct ?? "–"}%`} />
                  <VitalTile label="NEWS2" value={`${overview.latest_vitals.news2_score ?? "–"}`} />
                </div>
              ) : (
                <p className="text-sm text-slate-400">No vitals recorded.</p>
              )}
              {overview.weight_trend.length > 0 && (
                <div className="mt-4 border-t border-slate-100 pt-3">
                  <p className="mb-2 text-xs uppercase tracking-wide text-slate-400">Weight</p>
                  <div className="flex flex-wrap gap-2">
                    {overview.weight_trend.map((point) => (
                      <div key={point.recorded_at} className="rounded-lg bg-slate-50 px-2.5 py-1.5 text-center">
                        <p className="text-sm font-semibold text-slate-900">{point.weight_kg}kg</p>
                        <p className="text-[11px] text-slate-500">{formatDateTime(point.recorded_at)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>

            <Card>
              <CardHeader
                title="Recent Activity"
                action={
                  activity.length > 0 ? (
                    <button type="button" onClick={() => setTab("Activity")} className="text-xs font-medium text-brand-600 hover:text-brand-700">
                      View all
                    </button>
                  ) : undefined
                }
              />
              <div className="divide-y divide-slate-100">
                {activity.slice(0, 4).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setTab("Activity")}
                    className="flex w-full items-center justify-between gap-2 py-2.5 text-left hover:bg-slate-50"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{item.title}</p>
                      <p className="truncate text-xs text-slate-400">{item.detail ?? formatDateTime(item.occurred_at)}</p>
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-slate-300" />
                  </button>
                ))}
                {activity.length === 0 && <p className="py-4 text-center text-sm text-slate-400">No activity recorded.</p>}
              </div>
            </Card>
          </div>

          {allGoals.length > 0 && (
            <Card>
              <CardHeader
                title="Care Plan Goals"
                action={
                  <button type="button" onClick={() => setTab("Care Plan")} className="text-xs font-medium text-brand-600 hover:text-brand-700">
                    View all
                  </button>
                }
              />
              <div className="flex flex-wrap gap-2">
                {allGoals.slice(0, 6).map((goal) => (
                  <div key={goal.id} className="flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1.5 text-sm">
                    <span className="text-slate-700">{goal.goal_text}</span>
                    <GoalStatusPill status={goal.status} />
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
            subtitle={`${careEvents.length} entries logged`}
            action={
              <Link to={`/residents/${id}/care-records`}>
                <Button>
                  <Plus className="h-4 w-4" />
                  Record Care
                </Button>
              </Link>
            }
          />
          {careEvents.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">No records yet.</p>
          ) : (
            <TileGrid>
              {careEvents.map((event) => {
                const tone = statusTone(event.status);
                return (
                  <button
                    key={event.id}
                    type="button"
                    onClick={() => setSelectedEvent(event)}
                    className={clsx(
                      "flex aspect-square flex-col items-center justify-center gap-1.5 rounded-xl border-2 bg-white p-2 text-center transition-shadow hover:shadow-sm",
                      tone.border,
                    )}
                  >
                    <span className={clsx("h-2 w-2 shrink-0 rounded-full", tone.dot)} />
                    <span className="line-clamp-2 text-xs font-medium leading-tight text-slate-900">{event.template_name}</span>
                    <span className="text-[11px] text-slate-400">{formatDateTime(event.occurred_at)}</span>
                  </button>
                );
              })}
            </TileGrid>
          )}
        </Card>
      )}

      {selectedEvent && (
        <Modal title={selectedEvent.template_name} onClose={() => setSelectedEvent(null)}>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-500">{selectedEvent.category_name}</p>
              <span className={clsx("rounded-full px-2.5 py-1 text-xs font-medium", statusTone(selectedEvent.status).badge)}>
                {statusTone(selectedEvent.status).label}
              </span>
            </div>
            <p className="text-sm text-slate-500">
              {formatDateTime(selectedEvent.occurred_at)}
              {selectedEvent.duration_minutes != null ? ` · ${selectedEvent.duration_minutes} min` : ""}
            </p>
            <p className="text-sm text-slate-500">Performed by {selectedEvent.recorded_by_name ?? "Unknown"}</p>

            {selectedEvent.summary && (
              <div className="rounded-lg bg-slate-50 px-3 py-2.5">
                <p className="text-sm text-slate-700">{selectedEvent.summary}</p>
              </div>
            )}
          </div>
        </Modal>
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
