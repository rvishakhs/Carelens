import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Pill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import { CARE_RECORDS, RESIDENTS } from "@/lib/mockData";

const CATEGORY_TONE: Record<string, "emerald" | "sky" | "indigo" | "amber" | "rose" | "slate"> = {
  Nutrition: "emerald",
  Medical: "rose",
  Mobility: "sky",
  Activities: "indigo",
  "Personal Care": "amber",
};

function residentName(id: string) {
  return RESIDENTS.find((r) => r.id === id)?.name ?? "Unknown resident";
}

export function CareRecordsPage() {
  const [showModal, setShowModal] = useState(false);

  return (
    <div>
      <PageHeader
        title="Care Records"
        subtitle="Daily log of care activity across all residents"
        actions={
          <Button onClick={() => setShowModal(true)}>
            <Plus className="h-4 w-4" />
            Add Care Record
          </Button>
        }
      />

      <div className="space-y-4">
        {CARE_RECORDS.map((day) => (
          <Card key={day.date}>
            <CardHeader title={day.date} subtitle={`${day.entries.length} entries`} />
            <div className="divide-y divide-slate-100">
              {day.entries.map((entry) => (
                <div key={entry.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900">{entry.title}</p>
                    <p className="truncate text-xs text-slate-500">
                      {residentName(entry.residentId)} · {entry.staff}
                    </p>
                  </div>
                  <Pill tone={CATEGORY_TONE[entry.category] ?? "slate"}>{entry.category}</Pill>
                  <span className="w-16 shrink-0 text-right text-xs text-slate-400">{entry.time}</span>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      {showModal && (
        <Modal title="Add Care Record" onClose={() => setShowModal(false)}>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              setShowModal(false);
            }}
          >
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Resident</label>
              <select className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100">
                {RESIDENTS.map((r) => (
                  <option key={r.id}>{r.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Category</label>
              <select className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100">
                {Object.keys(CATEGORY_TONE).map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-700">Notes</label>
              <textarea
                rows={3}
                placeholder="Add details about this care activity…"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="secondary" onClick={() => setShowModal(false)}>
                Cancel
              </Button>
              <Button type="submit">Save Record</Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
