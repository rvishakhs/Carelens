export type CareStatus = "good" | "attention" | "high_risk";

export interface ResidentFlags {
  dnr?: boolean;
  allergies?: boolean;
  diabetic?: boolean;
}

export interface Resident {
  id: string;
  name: string;
  preferredName?: string;
  room: string;
  age: number;
  dob: string;
  gender: "Male" | "Female";
  careStatus: CareStatus;
  primaryNeeds: string[];
  lastActivity: string;
  initials: string;
  avatarColor: string;
  flags?: ResidentFlags;
  primaryNurse?: string;
  unit: string;
}

export interface CareRecordEntry {
  id: string;
  residentId: string;
  time: string;
  title: string;
  category: string;
  staff: string;
}

export interface CareRecordDay {
  date: string;
  entries: CareRecordEntry[];
}

export type GoalStatus = "on_track" | "at_risk" | "off_track";

export interface CarePlanGoal {
  id: string;
  title: string;
  description: string;
  status: GoalStatus;
}

export interface KeyMetric {
  label: string;
  value: string;
  status: "good" | "improved" | "stable" | "attention";
}

export interface ReportItem {
  id: string;
  title: string;
  generatedDate: string;
  category: string;
  icon: string;
}

export type StaffDutyStatus = "on_duty" | "off_duty";

export interface StaffMember {
  id: string;
  name: string;
  role: string;
  status: StaffDutyStatus;
  shift?: string;
  initials: string;
  avatarColor: string;
}

export type CalendarEventCategory =
  | "medication"
  | "personal_care"
  | "meal"
  | "activity"
  | "physiotherapy";

export interface CalendarEvent {
  id: string;
  day: string;
  time: string;
  title: string;
  meta: string;
  category: CalendarEventCategory;
}

export interface ActivityItem {
  id: string;
  title: string;
  meta: string;
  time: string;
  icon: string;
}

export interface AttentionResident {
  id: string;
  name: string;
  room: string;
  issue: string;
}

export type MedicationStatus = "given" | "due" | "missed";

export interface Medication {
  id: string;
  residentId: string;
  name: string;
  dosage: string;
  time: string;
  status: MedicationStatus;
}

// Mirrors app/modules/identity/models.py's Role enum.
export type UserRole = "carer" | "nurse" | "manager" | "family" | "emergency" | "system_admin" | "admin" | "headoffice";

// The subset a manager's "add staff" flow is allowed to hand out --
// app/modules/identity/service.py's _STAFF_CREATABLE_ROLES.
export type StaffRole = "carer" | "nurse";

export interface CurrentUser {
    id: string;
    care_home_id: string;
    care_home_name: string;
    role: UserRole;
    email: string;
    display_name: string;
    floor_ids: string[];
}

// GET /identity/staff -- mirrors app/modules/identity/schemas.py's UserRead.
export interface Staff {
    id: string;
    email: string;
    display_name: string;
    role: UserRole;
    is_active: boolean;
}

// POST /identity/staff request body -- mirrors StaffCreate.
export interface StaffCreateInput {
    email: string;
    display_name: string;
    role: StaffRole;
}

// POST /identity/staff response -- mirrors StaffCreated. temporary_password is only
// ever present here, right after creation; it's never returned by any other endpoint.
export interface StaffCreated {
    id: string;
    email: string;
    display_name: string;
    role: StaffRole;
    temporary_password: string;
}

// PATCH /identity/staff/{id} request body -- mirrors StaffUpdate. Both optional; only
// the fields provided change. role stays restricted to carer/nurse, same as creation.
export interface StaffUpdateInput {
    role?: StaffRole;
    is_active?: boolean;
}

// POST /identity/staff/{id}/reset-password response -- mirrors StaffCredentials.
// temporary_password is only ever present here, same one-time rule as StaffCreated.
export interface StaffCredentials {
    id: string;
    email: string;
    display_name: string;
    temporary_password: string;
}
