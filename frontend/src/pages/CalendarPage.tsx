import { Activity, Dumbbell, Pill as PillIcon, Sparkles, Utensils } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/layout/PageHeader";
import { CALENDAR_DATES, CALENDAR_DAYS, CALENDAR_EVENTS } from "@/lib/mockData";
import type { CalendarEventCategory } from "@/types";

const CATEGORY_ICON: Record<CalendarEventCategory, LucideIcon> = {
  medication: PillIcon,
  personal_care: Activity,
  meal: Utensils,
  activity: Sparkles,
  physiotherapy: Dumbbell,
};

const CATEGORY_STYLE: Record<CalendarEventCategory, string> = {
  medication: "bg-rose-50 text-rose-600",
  personal_care: "bg-amber-50 text-amber-600",
  meal: "bg-emerald-50 text-emerald-600",
  activity: "bg-indigo-50 text-indigo-600",
  physiotherapy: "bg-sky-50 text-sky-600",
};

export function CalendarPage() {
  const [activeDay, setActiveDay] = useState("TUE");
  const events = CALENDAR_EVENTS.filter((e) => e.day === activeDay);

  return (
    <div>
      <PageHeader title="Calendar" subtitle="Weekly schedule of care activities" />

      <Card className="mb-4">
        <div className="grid grid-cols-7 gap-2">
          {CALENDAR_DAYS.map((day, idx) => (
            <button
              key={day}
              onClick={() => setActiveDay(day)}
              className={`flex flex-col items-center gap-1 rounded-xl py-3 text-sm font-medium transition-colors ${
                activeDay === day ? "bg-brand-600 text-white" : "bg-slate-50 text-slate-600 hover:bg-slate-100"
              }`}
            >
              <span className="text-xs opacity-80">{day}</span>
              <span className="text-lg">{CALENDAR_DATES[idx]}</span>
            </button>
          ))}
        </div>
      </Card>

      <Card>
        <div className="divide-y divide-slate-100">
          {events.map((event) => {
            const Icon = CATEGORY_ICON[event.category];
            return (
              <div key={event.id} className="flex items-center gap-4 py-4">
                <span className="w-20 shrink-0 text-sm font-medium text-slate-500">{event.time}</span>
                <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${CATEGORY_STYLE[event.category]}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900">{event.title}</p>
                  <p className="truncate text-xs text-slate-500">{event.meta}</p>
                </div>
              </div>
            );
          })}
          {events.length === 0 && <p className="py-10 text-center text-sm text-slate-400">No scheduled events for this day.</p>}
        </div>
      </Card>
    </div>
  );
}
