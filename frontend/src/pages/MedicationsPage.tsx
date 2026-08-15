import { useEffect, useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import type { MedicationSchedule, MedicationScheduleStatus } from "@/types";
import { avatarColorFor, fetchMedicationSchedule } from "@/utils/helper";

const STATUS_TONE: Record<MedicationScheduleStatus, "emerald" | "amber" | "rose"> = {
  given: "emerald",
  due: "amber",
  missed: "rose",
};

const STATUS_LABEL: Record<MedicationScheduleStatus, string> = {
  given: "Given",
  due: "Due",
  missed: "Missed",
};

function initialsFromDisplayName(name: string) {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

function formatTime(iso: string | null) {
  if (!iso) return "PRN";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function MedicationsPage() {
  const [schedule, setSchedule] = useState<MedicationSchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMedicationSchedule()
      .then(setSchedule)
      .catch((err) => {
        console.error(err);
        setError("Unable to load the medication schedule");
      })
      .finally(() => setLoading(false));
  }, []);

  const entries = schedule?.entries ?? [];
  const givenCount = entries.filter((m) => m.status === "given").length;
  const missedCount = entries.filter((m) => m.status === "missed").length;

  return (
    <div>
      <PageHeader
        title="Medications"
        subtitle={
          schedule
            ? `${givenCount} given · ${missedCount} missed on ${new Date(schedule.day).toLocaleDateString()}`
            : "Loading…"
        }
      />

      {error && <div className="mb-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      <Card padded={false}>
        <div className="divide-y divide-slate-100">
          {entries.map((med) => (
            <div key={med.medication_event_id ?? `${med.medication_id}-${med.scheduled_for}`} className="flex items-center gap-4 px-5 py-4">
              <Avatar initials={initialsFromDisplayName(med.resident_display_name)} colorClass={avatarColorFor(med.resident_id)} size="sm" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-900">{med.resident_display_name}</p>
                <p className="truncate text-xs text-slate-500">
                  {med.drug_name} · {med.dose}
                </p>
              </div>
              <span className="w-20 shrink-0 text-sm text-slate-500">{formatTime(med.scheduled_for)}</span>
              <Pill tone={STATUS_TONE[med.status]} className="shrink-0">
                {STATUS_LABEL[med.status]}
              </Pill>
            </div>
          ))}
          {!loading && entries.length === 0 && (
            <p className="py-8 text-center text-sm text-slate-400">No medication schedule data available.</p>
          )}
          {loading && <p className="py-8 text-center text-sm text-slate-400">Loading medications…</p>}
        </div>
      </Card>
    </div>
  );
}
