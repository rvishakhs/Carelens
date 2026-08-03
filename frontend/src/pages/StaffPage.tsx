import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import { STAFF } from "@/lib/mockData";

export function StaffPage() {
  const onDuty = STAFF.filter((s) => s.status === "on_duty").length;

  return (
    <div>
      <PageHeader title="Staff" subtitle={`${onDuty} of ${STAFF.length} staff on duty`} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {STAFF.map((member) => (
          <Card key={member.id} className="flex items-center gap-4">
            <Avatar initials={member.initials} colorClass={member.avatarColor} size="lg" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-900">{member.name}</p>
              <p className="truncate text-xs text-slate-500">{member.role}</p>
              {member.shift && <p className="mt-1 truncate text-xs text-slate-400">{member.shift}</p>}
            </div>
            <Pill tone={member.status === "on_duty" ? "emerald" : "slate"}>
              {member.status === "on_duty" ? "On Duty" : "Off Duty"}
            </Pill>
          </Card>
        ))}
      </div>
    </div>
  );
}
