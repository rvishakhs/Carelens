import { AlertTriangle, Cookie, HeartPulse, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { StatusPill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import type { Resident } from "@/types";
import { avatarColorFor, calculateAge, fetchResidents, formatDomainLabel, initialsFor, timeAgo } from "@/utils/helper";

const ROW_COLUMNS = "grid-cols-[minmax(0,2.2fr)_100px_150px_120px_minmax(0,1.6fr)_110px]";

export function ResidentsPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [unit, setUnit] = useState("All Units");
  const [residents, setResidents] = useState<Resident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadResidents = async () => {
      try {
        setLoading(true);
        const data = await fetchResidents();
        setResidents(data);
      } catch (err) {
        console.error(err);
        setError("Unable to load residents");
      } finally {
        setLoading(false);
      }
    };

    loadResidents();
  }, []);

  const units = useMemo(() => {
    const names = new Set(residents.map((r) => r.floor_name).filter((n): n is string => !!n));
    return ["All Units", ...Array.from(names).sort()];
  }, [residents]);

  const filtered = useMemo(() => {
    return residents.filter((r) => {
      const matchesUnit = unit === "All Units" || r.floor_name === unit;

      const matchesQuery =
        !query.trim() ||
        `${r.first_name} ${r.last_name}`.toLowerCase().includes(query.toLowerCase()) ||
        (r.room_number ?? "").toLowerCase().includes(query.toLowerCase());

      return matchesUnit && matchesQuery;
    });
  }, [residents, query, unit]);

  return (
    <div>
      <PageHeader title="Residents" subtitle={`${residents.length} residents across your care home`} />

      {error && <div className="mb-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      <div className="mb-6 flex flex-wrap items-center gap-3">
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
          {units.map((u) => (
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

      <div className={`grid ${ROW_COLUMNS} gap-4 border-b border-slate-200 px-4 pb-2.5 text-xs font-medium uppercase tracking-wide text-slate-400`}>
        <span>Resident</span>
        <span>Room</span>
        <span>Age / DOB</span>
        <span>Status</span>
        <span>Primary Needs</span>
        <span>Last Activity</span>
      </div>

      <div>
        {!loading &&
          filtered.map((resident) => (
            <div
              key={resident.id}
              onClick={() => navigate(`/residents/${resident.id}`)}
              className={`grid ${ROW_COLUMNS} items-center gap-4 rounded-xl border-b border-slate-200/60 px-4 py-3.5 text-sm transition-colors last:border-0 hover:bg-white hover:shadow-sm cursor-pointer`}
            >
              <div className="flex min-w-0 items-center gap-3">
                <Avatar
                  initials={initialsFor(resident.first_name, resident.last_name)}
                  photoUrl={resident.photo_url}
                  colorClass={avatarColorFor(resident.id)}
                />
                <div className="min-w-0">
                  <p className="truncate font-medium text-slate-900">
                    {resident.preferred_name || resident.first_name} {resident.last_name}
                  </p>
                  {(resident.dnacpr || resident.has_allergies || resident.diabetic) && (
                    <div className="mt-0.5 flex items-center gap-1.5 text-slate-400">
                      {resident.dnacpr && (
                        <span title="DNACPR">
                          <AlertTriangle className="h-3.5 w-3.5" />
                        </span>
                      )}
                      {resident.has_allergies && (
                        <span title="Allergies">
                          <HeartPulse className="h-3.5 w-3.5" />
                        </span>
                      )}
                      {resident.diabetic && (
                        <span title="Diabetic">
                          <Cookie className="h-3.5 w-3.5" />
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <span className="text-slate-600">{resident.room_number ?? "—"}</span>
              <div className="whitespace-nowrap">
                <span className="font-medium text-slate-900">{calculateAge(resident.date_of_birth)}</span>{" "}
                <span className="text-slate-500">{resident.date_of_birth}</span>
              </div>
              <div>
                <StatusPill status={resident.status} />
              </div>
              <p className="truncate text-slate-600">
                {resident.active_care_domains.length > 0 ? resident.active_care_domains.map(formatDomainLabel).join(", ") : "—"}
              </p>
              <span className="text-slate-500">{timeAgo(resident.last_activity_at)}</span>
            </div>
          ))}

        {loading && <div className="py-12 text-center text-sm text-slate-400">Loading residents…</div>}
        {!loading && filtered.length === 0 && (
          <div className="py-12 text-center text-sm text-slate-400">No residents match your search.</div>
        )}
      </div>
    </div>
  );
}
