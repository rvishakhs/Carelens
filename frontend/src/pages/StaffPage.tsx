import { Check, Copy, Plus, ShieldOff } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Pill } from "@/components/ui/Pill";
import { PageHeader } from "@/components/layout/PageHeader";
import { getInitials } from "@/lib/format";
import { ROLE_LABELS, STAFF_CREATABLE_ROLES, canManageUsers } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { useStaffStore } from "@/store/staffStore";
import type { StaffRole } from "@/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100";
const labelClass = "mb-1.5 block text-sm font-medium text-slate-700";

function AddStaffForm({ onDone }: { onDone: () => void }) {
  const createStaff = useStaffStore((s) => s.createStaff);
  const isCreating = useStaffStore((s) => s.isCreating);

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<StaffRole>("carer");
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!displayName.trim() || !email.trim()) {
      setError("Enter a name and email address.");
      return;
    }
    setError("");
    try {
      await createStaff({ display_name: displayName.trim(), email: email.trim(), role });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create this staff member.");
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div>
        <label className={labelClass}>Full name</label>
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Emma Smith"
          className={inputClass}
        />
      </div>
      <div>
        <label className={labelClass}>Email address</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="emma@example.com"
          className={inputClass}
        />
        <p className="mt-1 text-xs text-slate-400">This becomes their Keycloak sign-in username.</p>
      </div>
      <div>
        <label className={labelClass}>Role</label>
        <select value={role} onChange={(e) => setRole(e.target.value as StaffRole)} className={inputClass}>
          {STAFF_CREATABLE_ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-sm text-rose-600">{error}</p>}

      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onDone} disabled={isCreating}>
          Cancel
        </Button>
        <Button type="submit" disabled={isCreating}>
          {isCreating ? "Creating…" : "Create Staff Member"}
        </Button>
      </div>
    </form>
  );
}

function CredentialsModal({ password, onClose }: { password: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(password);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Modal title="Staff Member Created" onClose={onClose}>
      <p className="text-sm text-slate-600">
        Share this temporary password with them directly -- it won't be shown again. Keycloak will ask them to set a
        new password the first time they sign in.
      </p>
      <div className="mt-4 flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2.5">
        <code className="truncate text-sm font-medium text-slate-900">{password}</code>
        <Button type="button" variant="secondary" onClick={handleCopy} className="shrink-0">
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <div className="mt-6 flex justify-end">
        <Button type="button" onClick={onClose}>
          Done
        </Button>
      </div>
    </Modal>
  );
}

export function StaffPage() {
  const currentUser = useAuthStore((s) => s.user);
  const { staff, isLoading, error, lastCreated, fetchStaff, dismissLastCreated } = useStaffStore();
  const [showAddModal, setShowAddModal] = useState(false);

  const allowed = canManageUsers(currentUser?.role);

  useEffect(() => {
    if (allowed) void fetchStaff();
  }, [allowed]);

  if (!allowed) {
    return (
      <div>
        <PageHeader title="Staff" />
        <Card className="flex flex-col items-center gap-3 py-12 text-center">
          <ShieldOff className="h-8 w-8 text-slate-300" />
          <p className="text-sm text-slate-500">
            You don't have permission to view staff management. Ask a manager if you need access.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Staff"
        subtitle={`${staff.length} staff member${staff.length === 1 ? "" : "s"} at your care home`}
        actions={
          <Button onClick={() => setShowAddModal(true)}>
            <Plus className="h-4 w-4" />
            Add Staff
          </Button>
        }
      />

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-sm text-slate-400">Loading staff…</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {staff.map((member) => (
            <Card key={member.id} className="flex items-center gap-4">
              <Avatar initials={getInitials(member.display_name)} size="lg" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-900">{member.display_name}</p>
                <p className="truncate text-xs text-slate-500">{member.email}</p>
                <Pill tone="indigo" className="mt-1.5">
                  {ROLE_LABELS[member.role]}
                </Pill>
              </div>
              <Pill tone={member.is_active ? "emerald" : "slate"}>{member.is_active ? "Active" : "Inactive"}</Pill>
            </Card>
          ))}

          {staff.length === 0 && (
            <div className="col-span-full py-12 text-center text-sm text-slate-400">
              No staff members yet -- add your first carer or nurse to get started.
            </div>
          )}
        </div>
      )}

      {showAddModal && (
        <Modal title="Add Staff Member" onClose={() => setShowAddModal(false)}>
          <AddStaffForm onDone={() => setShowAddModal(false)} />
        </Modal>
      )}

      {lastCreated && <CredentialsModal password={lastCreated.temporary_password} onClose={dismissLastCreated} />}
    </div>
  );
}
