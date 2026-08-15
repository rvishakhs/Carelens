/**
 * Static sample data for the screens not yet wired to the backend (Dashboard,
 * AI Insights, Calendar, Reports, Care Records, Staff roster shift display). Residents,
 * Medications and Care Plans are real (see @/lib/api / @/lib/residents) -- the mock
 * resident shape here is deliberately its own type (`MockResident`), not the real
 * `Resident` from @/types, since it carries fields (name/room/dob/avatarColor/...)
 * the backend doesn't return.
 */
import type {
  ActivityItem,
  AttentionResident,
  CalendarEvent,
  KeyMetric,
  ReportItem,
  StaffMember,
} from "@/types";

export const CARE_HOMES = ["Green Meadows Care Home", "Riverside Lodge", "Oakfield House"];

interface MockResident {
  id: string;
  name: string;
  room: string;
  age: number;
  dob: string;
  gender: "Male" | "Female";
  careStatus: "good" | "attention" | "high_risk";
  primaryNeeds: string[];
  lastActivity: string;
  initials: string;
  avatarColor: string;
  flags?: { dnr?: boolean; allergies?: boolean; diabetic?: boolean };
  primaryNurse?: string;
  unit: string;
}

export const MOCK_RESIDENTS: MockResident[] = [
  {
    id: "r1",
    name: "Margaret Smith",
    room: "Room 12",
    age: 82,
    dob: "12 Apr 1942",
    gender: "Female",
    careStatus: "good",
    primaryNeeds: ["Nutrition", "Mobility"],
    lastActivity: "15 min ago",
    initials: "MS",
    avatarColor: "bg-rose-200 text-rose-800",
    flags: { dnr: true, allergies: true, diabetic: true },
    primaryNurse: "Sarah Johnson",
    unit: "Dementia Unit",
  },
  {
    id: "r2",
    name: "James Brown",
    room: "Room 5",
    age: 75,
    dob: "23 May 1949",
    gender: "Male",
    careStatus: "attention",
    primaryNeeds: ["Medication", "Mood"],
    lastActivity: "25 min ago",
    initials: "JB",
    avatarColor: "bg-blue-200 text-blue-800",
    flags: { allergies: true },
    primaryNurse: "Sarah Johnson",
    unit: "Residential",
  },
  {
    id: "r3",
    name: "Patricia Williams",
    room: "Room 8",
    age: 68,
    dob: "3 Sep 1956",
    gender: "Female",
    careStatus: "high_risk",
    primaryNeeds: ["Mobility", "Falls Risk"],
    lastActivity: "45 min ago",
    initials: "PW",
    avatarColor: "bg-amber-200 text-amber-800",
    flags: { dnr: true },
    primaryNurse: "Michael Lee",
    unit: "Nursing",
  },
  {
    id: "r4",
    name: "Michael Lee",
    room: "Room 15",
    age: 71,
    dob: "17 Feb 1953",
    gender: "Male",
    careStatus: "good",
    primaryNeeds: ["Nutrition", "Diabetes"],
    lastActivity: "1 hr ago",
    initials: "ML",
    avatarColor: "bg-emerald-200 text-emerald-800",
    flags: { diabetic: true },
    primaryNurse: "Sarah Johnson",
    unit: "Residential",
  },
  {
    id: "r5",
    name: "Linda Thomas",
    room: "Room 3",
    age: 79,
    dob: "8 Jul 1944",
    gender: "Female",
    careStatus: "attention",
    primaryNeeds: ["Pain", "Sleep"],
    lastActivity: "2 hrs ago",
    initials: "LT",
    avatarColor: "bg-violet-200 text-violet-800",
    primaryNurse: "Michael Lee",
    unit: "Nursing",
  },
  {
    id: "r6",
    name: "Robert Davis",
    room: "Room 11",
    age: 85,
    dob: "30 Jan 1939",
    gender: "Male",
    careStatus: "good",
    primaryNeeds: ["Continence", "Mobility"],
    lastActivity: "3 hrs ago",
    initials: "RD",
    avatarColor: "bg-cyan-200 text-cyan-800",
    primaryNurse: "Sarah Johnson",
    unit: "Dementia Unit",
  },
  {
    id: "r7",
    name: "Barbara Wilson",
    room: "Room 6",
    age: 74,
    dob: "19 Mar 1950",
    gender: "Female",
    careStatus: "good",
    primaryNeeds: ["Nutrition", "Mood"],
    lastActivity: "4 hrs ago",
    initials: "BW",
    avatarColor: "bg-pink-200 text-pink-800",
    primaryNurse: "Michael Lee",
    unit: "Residential",
  },
  {
    id: "r8",
    name: "William Taylor",
    room: "Room 9",
    age: 69,
    dob: "27 Aug 1954",
    gender: "Male",
    careStatus: "attention",
    primaryNeeds: ["Medication", "BP"],
    lastActivity: "5 hrs ago",
    initials: "WT",
    avatarColor: "bg-indigo-200 text-indigo-800",
    primaryNurse: "Sarah Johnson",
    unit: "Nursing",
  },
];

export const ATTENTION_RESIDENTS: AttentionResident[] = [
  { id: "r1", name: "Margaret Smith", room: "Room 12", issue: "Low food intake" },
  { id: "r2", name: "James Brown", room: "Room 5", issue: "Missed medication" },
  { id: "r3", name: "Patricia Williams", room: "Room 8", issue: "Low mood detected" },
];

export const RECENT_ACTIVITY: ActivityItem[] = [
  { id: "a1", title: "Sarah Johnson", meta: "Logged medication for James Brown", time: "10 min ago", icon: "pill" },
  { id: "a2", title: "Michael Lee", meta: "Updated care plan for Margaret Smith", time: "25 min ago", icon: "clipboard" },
  { id: "a3", title: "Emma Davis", meta: "Added note for Patricia Williams", time: "45 min ago", icon: "sticky-note" },
];

interface MockCareRecordEntry {
  id: string;
  residentId: string;
  time: string;
  title: string;
  category: string;
  staff: string;
}

interface MockCareRecordDay {
  date: string;
  entries: MockCareRecordEntry[];
}

export const CARE_RECORDS: MockCareRecordDay[] = [
  {
    date: "Tuesday, 9 July 2024",
    entries: [
      { id: "c1", residentId: "r1", time: "8:15 AM", title: "Breakfast", category: "Nutrition", staff: "Sarah Johnson" },
      { id: "c2", residentId: "r1", time: "9:00 AM", title: "Medication", category: "Medical", staff: "Sarah Johnson" },
      { id: "c3", residentId: "r4", time: "10:30 AM", title: "Physiotherapy", category: "Mobility", staff: "Michael Lee" },
      { id: "c4", residentId: "r1", time: "12:30 PM", title: "Lunch", category: "Nutrition", staff: "Sarah Johnson" },
      { id: "c5", residentId: "r7", time: "2:00 PM", title: "Bingo Activity", category: "Activities", staff: "Activities Coordinator" },
      { id: "c6", residentId: "r1", time: "6:00 PM", title: "Dinner", category: "Nutrition", staff: "Sarah Johnson" },
      { id: "c7", residentId: "r1", time: "8:30 PM", title: "Night Routine", category: "Personal Care", staff: "Sarah Johnson" },
    ],
  },
  {
    date: "Monday, 8 July 2024",
    entries: [
      { id: "c8", residentId: "r1", time: "8:00 AM", title: "Breakfast", category: "Nutrition", staff: "Sarah Johnson" },
      { id: "c9", residentId: "r1", time: "9:00 AM", title: "Medication", category: "Medical", staff: "Sarah Johnson" },
    ],
  },
];

export const KEY_METRICS: KeyMetric[] = [
  { label: "Nutrition", value: "85%", status: "good" },
  { label: "Hydration", value: "1.6L", status: "good" },
  { label: "Mobility", value: "Stable", status: "stable" },
  { label: "Mood", value: "Stable", status: "stable" },
  { label: "Sleep", value: "7.5h", status: "good" },
];

export const AI_RECOMMENDATIONS = [
  "Encourage 1500ml fluid intake in the afternoon",
  "Continue daily walks",
  "Consider adding variety to lunch menu",
];

export const AI_CHECKLIST = [
  "Nutrition intake 85% of meals",
  "Hydration intake 1.6L",
  "Participated in 3 activities",
  "Slept well last night (7.5 hours)",
  "No concerns identified",
];

export const REPORTS: ReportItem[] = [
  { id: "rep1", title: "Daily Summary Report", generatedDate: "9 Jul 2024", category: "Clinical", icon: "file-text" },
  { id: "rep2", title: "Weekly Summary Report", generatedDate: "7 Jul 2024", category: "Clinical", icon: "file-text" },
  { id: "rep3", title: "Nutrition Report", generatedDate: "8 Jul 2024", category: "Nutrition", icon: "utensils" },
  { id: "rep4", title: "Hydration Report", generatedDate: "8 Jul 2024", category: "Nutrition", icon: "droplet" },
  { id: "rep5", title: "Mobility Report", generatedDate: "8 Jul 2024", category: "Mobility", icon: "footprints" },
  { id: "rep6", title: "Mood & Behaviour Report", generatedDate: "8 Jul 2024", category: "Behaviour", icon: "heart" },
  { id: "rep7", title: "Sleep Quality Report", generatedDate: "8 Jul 2024", category: "Sleep", icon: "moon" },
  { id: "rep8", title: "Continence Report", generatedDate: "8 Jul 2024", category: "Continence", icon: "shield" },
];

export const STAFF: StaffMember[] = [
  { id: "s1", name: "Sarah Johnson", role: "Senior Nurse", status: "on_duty", shift: "7:00 AM – 7:00 PM", initials: "SJ", avatarColor: "bg-brand-200 text-brand-900" },
  { id: "s2", name: "Michael Lee", role: "Care Assistant", status: "on_duty", shift: "7:00 AM – 7:00 PM", initials: "ML", avatarColor: "bg-blue-200 text-blue-900" },
  { id: "s3", name: "Emma Davis", role: "Care Assistant", status: "on_duty", shift: "7:00 AM – 3:00 PM", initials: "ED", avatarColor: "bg-amber-200 text-amber-900" },
  { id: "s4", name: "Priya Patel", role: "Registered Nurse", status: "off_duty", shift: "Night shift", initials: "PP", avatarColor: "bg-violet-200 text-violet-900" },
  { id: "s5", name: "Tom Wright", role: "Physiotherapist", status: "on_duty", shift: "9:00 AM – 5:00 PM", initials: "TW", avatarColor: "bg-emerald-200 text-emerald-900" },
];

export const CALENDAR_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
export const CALENDAR_DATES = [8, 9, 10, 11, 12, 13, 14];

export const CALENDAR_EVENTS: CalendarEvent[] = [
  { id: "e1", day: "TUE", time: "9:00 AM", title: "Medications", meta: "8 residents", category: "medication" },
  { id: "e2", day: "TUE", time: "10:00 AM", title: "Personal Care", meta: "6 residents", category: "personal_care" },
  { id: "e3", day: "TUE", time: "11:00 AM", title: "Physiotherapy", meta: "James Brown", category: "physiotherapy" },
  { id: "e4", day: "TUE", time: "12:00 PM", title: "Lunch", meta: "32 residents", category: "meal" },
  { id: "e5", day: "TUE", time: "2:00 PM", title: "Bingo Activity", meta: "All residents", category: "activity" },
  { id: "e6", day: "TUE", time: "6:00 PM", title: "Dinner", meta: "32 residents", category: "meal" },
];

export const DASHBOARD_STATS = {
  residents: { value: 32, delta: "+2 this month" },
  careRecords: { value: 128, delta: "Today" },
  aiAlerts: { value: 5, delta: "Requires attention" },
  medications: { value: 18, delta: "Due today" },
  staffOnDuty: { value: 12, delta: "View roster" },
};

// Categorical palette validated with the dataviz skill's validator (fixed hue order,
// chroma floor + CVD-separation + lightness band all pass -- see conversation notes).
export const CARE_OVERVIEW_BREAKDOWN = [
  { label: "Personal Care", value: 38, color: "#0f9488" },
  { label: "Nutrition", value: 32, color: "#f59e0b" },
  { label: "Medications", value: 18, color: "#6366f1" },
  { label: "Mobility", value: 16, color: "#ec4899" },
  { label: "Activities", value: 14, color: "#0ea5e9" },
  { label: "Other", value: 10, color: "#65a30d" },
];
