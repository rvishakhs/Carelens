import { AlertTriangle, Cookie, HeartPulse, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import { RESIDENTS } from "@/lib/mockData";

const UNITS = ["All Units", "Dementia Unit", "Residential", "Nursing"];

export function ResidentsPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [unit, setUnit] = useState("All Units");

  const filtered = useMemo(() => {
    return RESIDENTS.filter((r) => {
      const matchesUnit = unit === "All Units" || r.unit === unit;
      const matchesQuery =
        !query.trim() ||
        r.name.toLowerCase().includes(query.toLowerCase()) ||
        r.room.toLowerCase().includes(query.toLowerCase());
      return matchesUnit && matchesQuery;
    });
  }, [query, unit]);

  return (
    <div>
      <PageHeader title="Residents" subtitle={`${RESIDENTS.length} residents across your care home`} />

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search residents by name or room…"
            className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 shadow-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
          />
        </div>
        <div className="flex gap-1 overflow-x-auto rounded-lg border border-slate-200 bg-white p-1 shadow-sm scrollbar-none">
          {UNITS.map((u) => (
            <button
              key={u}
              onClick={() => setUnit(u)}
              className={`shrink-0 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                unit === u ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {u}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((resident) => (
          <Card
            key={resident.id}
            className="cursor-pointer transition-shadow hover:shadow-md"
            onClick={() => navigate(`/residents/${resident.id}`)}
          >
            <div className="flex items-start gap-3">
              <Avatar initials={resident.initials} colorClass={resident.avatarColor} size="lg" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="truncate font-semibold text-slate-900">{resident.name}</h3>
                  <StatusPill status={resident.careStatus} />
                </div>
                <p className="text-sm text-slate-500">
                  {resident.room} · {resident.age} yrs · {resident.unit}
                </p>

                <div className="mt-2 flex flex-wrap gap-1.5">
                  {resident.primaryNeeds.map((need) => (
                    <span key={need} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {need}
                    </span>
                  ))}
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-400">
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
                  </div>
                  <span className="text-xs text-slate-400">Active {resident.lastActivity}</span>
                </div>
              </div>
            </div>
          </Card>
        ))}

        {filtered.length === 0 && (
          <div className="col-span-full py-12 text-center text-sm text-slate-400">No residents match your search.</div>
        )}
      </div>
    </div>
  );
}
