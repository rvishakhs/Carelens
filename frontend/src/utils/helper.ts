import api from "@/lib/api";
import type {
  ActivityEntry,
  CarePlan,
  CareRecordEntry,
  MedicationSchedule,
  Resident,
  ResidentOverview,
} from "@/types";

export async function fetchResidents(): Promise<Resident[]> {
  const { data } = await api.get<Resident[]>("/residents");
  return data;
}

export async function fetchResidentOverview(residentId: string): Promise<ResidentOverview> {
  const { data } = await api.get<ResidentOverview>(`/residents/${residentId}/overview`);
  return data;
}

export async function fetchResidentCarePlan(residentId: string): Promise<CarePlan[]> {
  const { data } = await api.get<CarePlan[]>(`/residents/${residentId}/care-plan`);
  return data;
}

export async function fetchResidentCareRecords(residentId: string): Promise<CareRecordEntry[]> {
  const { data } = await api.get<CareRecordEntry[]>(`/residents/${residentId}/care-records`);
  return data;
}

export async function fetchResidentActivity(residentId: string): Promise<ActivityEntry[]> {
  const { data } = await api.get<ActivityEntry[]>(`/residents/${residentId}/activity`);
  return data;
}

export async function fetchAllCarePlans(): Promise<CarePlan[]> {
  const { data } = await api.get<CarePlan[]>("/care-plans");
  return data;
}

export async function fetchMedicationSchedule(): Promise<MedicationSchedule> {
  const { data } = await api.get<MedicationSchedule>("/medications/schedule");
  return data;
}

// Calculating age
export function calculateAge(dateOfBirth: Date | string): number {
  const dob = typeof dateOfBirth === "string" ? new Date(dateOfBirth) : dateOfBirth;
  const today = new Date();

  // Validate date
  if (isNaN(dob.getTime())) {
    throw new Error("Invalid date format");
  }

  let age = today.getFullYear() - dob.getFullYear();
  const monthDifference = today.getMonth() - dob.getMonth();

  // Subtract 1 year if the birthday hasn't occurred yet this year
  if (monthDifference < 0 || (monthDifference === 0 && today.getDate() < dob.getDate())) {
    age--;
  }

  return age;
}

/** Renders a past ISO timestamp as "just now" / "12 min ago" / "3 hr ago" / "5d ago". */
export function timeAgo(isoTimestamp: string | null): string {
  if (!isoTimestamp) return "No activity recorded";
  const diffMs = Date.now() - new Date(isoTimestamp).getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Deterministic avatar background/text color from a name, so the same resident
 * always gets the same color without the backend needing to store one. */
const AVATAR_COLORS = [
  "bg-rose-200 text-rose-800",
  "bg-blue-200 text-blue-800",
  "bg-amber-200 text-amber-800",
  "bg-emerald-200 text-emerald-800",
  "bg-violet-200 text-violet-800",
  "bg-cyan-200 text-cyan-800",
  "bg-pink-200 text-pink-800",
  "bg-indigo-200 text-indigo-800",
];

export function avatarColorFor(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

export function initialsFor(firstName: string, lastName: string): string {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

/** "mobility" / "nutrition_hydration" -> "Mobility" / "Nutrition Hydration". */
export function formatDomainLabel(domain: string): string {
  return domain
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
