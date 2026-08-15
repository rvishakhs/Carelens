// Mirrors app/modules/residents/models.py's ResidentStatus enum.
export type ResidentStatus = "active" | "discharged" | "hospitalized" | "archived";

// GET /residents -- mirrors app/modules/residents/schemas.py's ResidentListItem.
export interface Resident {
  id: string;
  first_name: string;
  last_name: string;
  preferred_name: string | null;
  date_of_birth: string;
  gender: string | null;
  room_number: string | null;
  floor_id: string | null;
  floor_name: string | null;
  status: ResidentStatus;
  dnacpr: boolean;
  has_allergies: boolean;
  diabetic: boolean;
  active_care_domains: string[];
  last_activity_at: string | null;
}

// GET /residents/{id}/overview -- mirrors ResidentOverview.
export interface Diagnosis {
  id: string;
  condition_name: string;
  icd10_code: string | null;
  diagnosed_date: string | null;
  is_primary: boolean;
  status: string;
  notes: string | null;
}

export interface Allergy {
  id: string;
  allergen: string;
  reaction: string | null;
  severity: string | null;
}

export interface Contact {
  id: string;
  full_name: string;
  relationship: string;
  is_next_of_kin: boolean;
  is_emergency_contact: boolean;
  phone: string | null;
  email: string | null;
}

export interface AdvanceDirective {
  id: string;
  directive_type: string;
  summary: string;
  review_due: string | null;
  is_current: boolean;
}

export interface LifeHistory {
  occupation: string | null;
  family_background: string | null;
  significant_events: string | null;
  hobbies_interests: string | null;
  important_relationships: string | null;
  faith_religion: string | null;
  cultural_background: string | null;
  military_veteran: boolean;
  free_text_narrative: string | null;
}

export interface Preference {
  category: string;
  preference: string;
  is_like: boolean;
  priority: number;
}

export interface VitalsSnapshot {
  recorded_at: string;
  blood_pressure_systolic: number | null;
  blood_pressure_diastolic: number | null;
  heart_rate_bpm: number | null;
  oxygen_saturation_pct: number | null;
  temperature_celsius: number | null;
  news2_score: number | null;
}

export interface WeightPoint {
  recorded_at: string;
  weight_kg: number;
}

export interface ResidentOverview {
  resident_id: string;
  diagnoses: Diagnosis[];
  allergies: Allergy[];
  contacts: Contact[];
  advance_directives: AdvanceDirective[];
  life_history: LifeHistory | null;
  top_preferences: Preference[];
  latest_vitals: VitalsSnapshot | null;
  weight_trend: WeightPoint[];
  mobility_level: string | null;
  falls_risk_level: string | null;
  skin_risk_level: string | null;
  active_medication_count: number;
  dnacpr: boolean;
}

// Mirrors care_plan_goals.status (migration 0020's care_plan_goal_status enum).
export type GoalStatus = "not_started" | "in_progress" | "improving" | "maintained" | "declining" | "achieved" | "discontinued";

export interface CarePlanGoal {
  id: string;
  goal_text: string;
  baseline: string | null;
  target: string | null;
  measurement: string | null;
  status: GoalStatus;
  review_date: string | null;
}

// GET /residents/{id}/care-plan and GET /care-plans -- mirrors CarePlanRead.
export interface CarePlan {
  id: string;
  resident_id: string;
  domain: string;
  goal: string;
  is_active: boolean;
  review_due: string | null;
  goals: CarePlanGoal[];
}

// GET /residents/{id}/care-records -- mirrors CareRecordEntry.
export interface CareRecordEntry {
  id: string;
  record_type: string;
  recorded_at: string;
  title: string;
  detail: string | null;
}

// GET /residents/{id}/activity -- mirrors ActivityEntry.
export interface ActivityEntry {
  id: string;
  entry_type: "activity" | "visit" | "appointment";
  occurred_at: string;
  title: string;
  detail: string | null;
}

// GET /medications/schedule -- mirrors MedicationSchedule/MedicationScheduleEntry.
export type MedicationScheduleStatus = "given" | "due" | "missed";

export interface MedicationScheduleEntry {
  medication_event_id: string | null;
  medication_id: string;
  resident_id: string;
  resident_display_name: string;
  drug_name: string;
  dose: string;
  scheduled_for: string | null;
  status: MedicationScheduleStatus;
}

export interface MedicationSchedule {
  day: string;
  entries: MedicationScheduleEntry[];
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
