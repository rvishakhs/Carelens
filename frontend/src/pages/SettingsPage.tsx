import { useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Card, CardHeader } from "@/components/ui/Card";
import { Pill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import { getInitials } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { useUiStore } from "@/store/uiStore";
import { CARE_HOMES } from "@/lib/mockData";

function Toggle({ defaultChecked = false }: { defaultChecked?: boolean }) {
  const [on, setOn] = useState(defaultChecked);
  return (
    <button
      onClick={() => setOn((v) => !v)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${on ? "bg-brand-600" : "bg-slate-200"}`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
          on ? "translate-x-5" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

export function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const selectedCareHome = useUiStore((s) => s.selectedCareHome);
  const setSelectedCareHome = useUiStore((s) => s.setSelectedCareHome);

  return (
    <div>
      <PageHeader title="Settings" subtitle="Manage your profile, care home and notification preferences" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Profile" subtitle="Your account details" />
          <div className="flex items-center gap-4">
            <Avatar initials={getInitials(user?.display_name)} size="lg" />
            <div>
              <p className="text-sm font-semibold text-slate-900">{user?.display_name}</p>
              <p className="text-sm text-slate-500">{user?.email}</p>
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2.5">
            <span className="text-sm text-slate-600">Access role</span>
            <Pill tone="indigo">{user && ROLE_LABELS[user.role]}</Pill>
          </div>
        </Card>

        <Card>
          <CardHeader title="Care Home" subtitle="Default location for your dashboard" />
          <div className="space-y-2">
            {CARE_HOMES.map((home) => (
              <button
                key={home}
                onClick={() => setSelectedCareHome(home)}
                className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${
                  selectedCareHome === home
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {home}
              </button>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Notifications" subtitle="Choose what you're alerted about" />
          <div className="space-y-4">
            {[
              ["AI insight alerts", true],
              ["Medication reminders", true],
              ["Care plan updates", false],
              ["Weekly summary email", false],
            ].map(([label, defaultChecked]) => (
              <div key={label as string} className="flex items-center justify-between">
                <span className="text-sm text-slate-700">{label}</span>
                <Toggle defaultChecked={defaultChecked as boolean} />
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Security" subtitle="Authentication is managed by your organisation's identity provider" />
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2.5">
              <span className="text-sm text-slate-600">Single sign-on</span>
              <Pill tone="emerald">Keycloak</Pill>
            </div>
            <p className="text-xs text-slate-400">
              Password changes and MFA are handled by Keycloak, not CareLens directly.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
