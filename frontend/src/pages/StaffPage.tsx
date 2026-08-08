import { Check, Copy, KeyRound, Plus, ShieldOff } from "lucide-react";
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
import type { Staff, StaffRole } from "@/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100";
const disabledInputClass =
  "w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500";
const labelClass = "mb-1.5 block text-sm font-medium text-slate-700";

function AddStaffForm({ careHomeName, onDone }: { careHomeName: string; onDone: () => void }) {
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
      <div>
        <label className={labelClass}>Care home</label>
        <input value={careHomeName} disabled className={disabledInputClass} />
        <p className="mt-1 text-xs text-slate-400">Staff are added to your care home.</p>
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

function CredentialsModal({
  displayName,
  password,
  onClose,
}: {
  displayName: string;
  password: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(password);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Modal title={`Temporary Password — ${displayName}`} onClose={onClose}>
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

function StaffCard({ member, isOwnAccount }: { member: Staff; isOwnAccount: boolean }) {
  const updateStaff = useStaffStore((s) => s.updateStaff);
  const resetPassword = useStaffStore((s) => s.resetPassword);
  const mutatingId = useStaffStore((s) => s.mutatingId);
  const isMutating = mutatingId === member.id;

  function handleRoleChange(role: StaffRole) {
    if (role !== member.role) void updateStaff(member.id, { role });
  }

  function handleToggleActive() {
    const next = !member.is_active;
    const verb = next ? "Reactivate" : "Deactivate";
    if (window.confirm(`${verb} ${member.display_name}? ${next ? "They'll" : "They will no longer"} be able to sign in.`)) {
      void updateStaff(member.id, { is_active: next });
    }
  }

  function handleResetPassword() {
    if (window.confirm(`Generate a new temporary password for ${member.display_name}? Their current password stops working immediately.`)) {
      void resetPassword(member.id);
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-4">
        <Avatar initials={getInitials(member.display_name)} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900">{member.display_name}</p>
          <p className="truncate text-xs text-slate-500">{member.email}</p>
        </div>
        <Pill tone={member.is_active ? "emerald" : "slate"}>{member.is_active ? "Active" : "Inactive"}</Pill>
      </div>

      {isOwnAccount ? (
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-400">
          This is your account -- role and active status are managed elsewhere.
        </p>
      ) : (
        <div className="flex items-center gap-2">
          <select
            value={member.role}
            disabled={isMutating}
            onChange={(e) => handleRoleChange(e.target.value as StaffRole)}
            className="flex-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-700 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:opacity-50"
          >
            {STAFF_CREATABLE_ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="secondary"
            onClick={handleResetPassword}
            disabled={isMutating}
            title="Reset password"
            className="px-2.5"
          >
            <KeyRound className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant={member.is_active ? "danger" : "secondary"}
            onClick={handleToggleActive}
            disabled={isMutating}
            className="px-2.5 text-xs"
          >
            {member.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        </div>
      )}
    </Card>
  );
}

export function StaffPage() {
  const currentUser = useAuthStore((s) => s.user);
  const { staff, isLoading, error, lastCredentials, fetchStaff, dismissCredentials } = useStaffStore();
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
        subtitle={`${staff.length} staff member${staff.length === 1 ? "" : "s"} at ${currentUser!.care_home_name}`}
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
            <StaffCard key={member.id} member={member} isOwnAccount={member.id === currentUser?.id} />
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
          <AddStaffForm careHomeName={currentUser!.care_home_name} onDone={() => setShowAddModal(false)} />
        </Modal>
      )}

      {lastCredentials && (
        <CredentialsModal
          displayName={lastCredentials.displayName}
          password={lastCredentials.temporaryPassword}
          onClose={dismissCredentials}
        />
      )}
    </div>
  );
}
