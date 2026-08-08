import type { UserRole } from "@/types";

export const ROLE_LABELS: Record<UserRole, string> = {
  carer: "Carer",
  nurse: "Nurse",
  manager: "Manager",
  admin: "Admin",
  headoffice: "Head Office",
  system_admin: "System Admin",
  family: "Family",
  emergency: "Emergency Access",
};

export const STAFF_CREATABLE_ROLES: { value: UserRole; label: string }[] = [
  { value: "carer", label: ROLE_LABELS.carer },
  { value: "nurse", label: ROLE_LABELS.nurse },
];

// Mirrors app/modules/identity/permissions.py's ROLE_PERMISSIONS[*] containing
// Permission.MANAGE_USERS -- UX gating only (hide the button/nav item, avoid a
// pointless 403 round-trip). The backend's require(Permission.MANAGE_USERS) on
// POST/GET /identity/staff is the actual enforcement; keep this set in sync with it
// by hand, it isn't fetched from the server.
const MANAGE_USERS_ROLES = new Set<UserRole>(["manager", "admin", "headoffice", "system_admin"]);

export function canManageUsers(role: UserRole | undefined): boolean {
  return !!role && MANAGE_USERS_ROLES.has(role);
}
