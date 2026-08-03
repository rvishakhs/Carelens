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

export interface AuthUser {
  name: string;
  role: string;
  initials: string;
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

export interface CurrentUser {
    id: string;
    care_home_id: string;
    role: string;
    email: string;
    display_name: string;
    floor_ids: string[];
}
