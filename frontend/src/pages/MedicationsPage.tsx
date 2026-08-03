import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import { MEDICATIONS, RESIDENTS } from "@/lib/mockData";
import type { MedicationStatus } from "@/types";

const STATUS_TONE: Record<MedicationStatus, "emerald" | "amber" | "rose"> = {
  given: "emerald",
  due: "amber",
  missed: "rose",
};

const STATUS_LABEL: Record<MedicationStatus, string> = {
  given: "Given",
  due: "Due",
  missed: "Missed",
};

function resident(id: string) {
  return RESIDENTS.find((r) => r.id === id);
}

export function MedicationsPage() {
  const dueCount = MEDICATIONS.filter((m) => m.status === "due").length;
  const missedCount = MEDICATIONS.filter((m) => m.status === "missed").length;

  return (
    <div>
      <PageHeader title="Medications" subtitle={`${dueCount} due · ${missedCount} missed today`} />

      <Card padded={false}>
        <div className="divide-y divide-slate-100">
          {MEDICATIONS.map((med) => {
            const r = resident(med.residentId);
            return (
              <div key={med.id} className="flex items-center gap-4 px-5 py-4">
                <Avatar initials={r?.initials ?? "?"} colorClass={r?.avatarColor} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900">{r?.name}</p>
                  <p className="truncate text-xs text-slate-500">
                    {med.name} · {med.dosage}
                  </p>
                </div>
                <span className="w-20 shrink-0 text-sm text-slate-500">{med.time}</span>
                <Pill tone={STATUS_TONE[med.status]} className="shrink-0">
                  {STATUS_LABEL[med.status]}
                </Pill>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
