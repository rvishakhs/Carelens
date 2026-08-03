import { Download, Droplet, FileText, Footprints, Heart, Moon, Shield, Utensils } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import { REPORTS } from "@/lib/mockData";

const ICONS: Record<string, LucideIcon> = {
  "file-text": FileText,
  utensils: Utensils,
  droplet: Droplet,
  footprints: Footprints,
  heart: Heart,
  moon: Moon,
  shield: Shield,
};

const CATEGORY_TONE: Record<string, "emerald" | "sky" | "indigo" | "amber" | "rose" | "slate"> = {
  Clinical: "indigo",
  Nutrition: "emerald",
  Mobility: "sky",
  Behaviour: "rose",
  Sleep: "slate",
  Continence: "amber",
};

export function ReportsPage() {
  return (
    <div>
      <PageHeader title="Reports" subtitle="Generated clinical and wellbeing summaries" />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {REPORTS.map((report) => {
          const Icon = ICONS[report.icon] ?? FileText;
          return (
            <Card key={report.id} className="flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                  <Icon className="h-5 w-5" />
                </div>
                <Pill tone={CATEGORY_TONE[report.category] ?? "slate"}>{report.category}</Pill>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">{report.title}</p>
                <p className="text-xs text-slate-500">Generated {report.generatedDate}</p>
              </div>
              <Button variant="secondary" className="mt-1 w-full justify-center">
                <Download className="h-4 w-4" />
                Download
              </Button>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
