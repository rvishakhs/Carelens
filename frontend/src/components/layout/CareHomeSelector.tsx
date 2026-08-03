import { Building2, ChevronDown } from "lucide-react";
import { useState } from "react";

import { CARE_HOMES } from "@/lib/mockData";
import { useUiStore } from "@/store/uiStore";

export function CareHomeSelector() {
  const [open, setOpen] = useState(false);
  const selected = useUiStore((s) => s.selectedCareHome);
  const setSelected = useUiStore((s) => s.setSelectedCareHome);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
      >
        <Building2 className="h-4 w-4 text-slate-400" />
        <span className="max-w-[10rem] truncate">{selected}</span>
        <ChevronDown className="h-4 w-4 text-slate-400" />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-56 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {CARE_HOMES.map((home) => (
            <button
              key={home}
              onMouseDown={() => setSelected(home)}
              className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
            >
              {home}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
