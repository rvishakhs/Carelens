import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import type { Resident } from "@/types";
import { avatarColorFor, calculateAge, fetchResidents, initialsFor } from "@/utils/helper";

export function CareRecordsPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [residents, setResidents] = useState<Resident[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchResidents()
      .then(setResidents)
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    if (!query.trim()) return residents;
    const q = query.toLowerCase();
    return residents.filter(
      (r) => `${r.first_name} ${r.last_name}`.toLowerCase().includes(q) || (r.room_number ?? "").toLowerCase().includes(q),
    );
  }, [residents, query]);

  return (
    <div>
      <PageHeader title="Care Records" subtitle="Choose a resident to record or review their care" />

      <div className="relative mb-5 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search residents by name or room…"
          className="w-full rounded-lg border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 shadow-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {!loading &&
          filtered.map((resident) => (
            <Card
              key={resident.id}
              className="cursor-pointer transition-shadow hover:shadow-md"
              onClick={() => navigate(`/residents/${resident.id}/care-records`)}
            >
              <div className="flex items-center gap-3">
                <Avatar
                  initials={initialsFor(resident.first_name, resident.last_name)}
                  colorClass={avatarColorFor(resident.id)}
                  size="lg"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="truncate font-semibold text-slate-900">
                      {resident.preferred_name || resident.first_name} {resident.last_name}
                    </h3>
                    <StatusPill status={resident.status} />
                  </div>
                  <p className="text-sm text-slate-500">
                    {resident.room_number ?? "No room"} · {calculateAge(resident.date_of_birth)} yrs · {resident.floor_name ?? "Unassigned"}
                  </p>
                </div>
              </div>
            </Card>
          ))}

        {loading && <div className="col-span-full py-12 text-center text-sm text-slate-400">Loading residents…</div>}
        {!loading && filtered.length === 0 && (
          <div className="col-span-full py-12 text-center text-sm text-slate-400">No residents match your search.</div>
        )}
      </div>
    </div>
  );
}
