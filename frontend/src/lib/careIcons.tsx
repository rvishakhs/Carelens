import {
  Accessibility,
  Activity,
  ClipboardList,
  Droplet,
  Heart,
  MessageCircle,
  Moon,
  Settings,
  Shield,
  Stethoscope,
  Toilet,
  Utensils,
  type LucideIcon,
} from "lucide-react";

// Maps care_categories.icon / care_templates icon strings (seeded in migration 0015)
// to lucide-react components. lucide-react has no "Wheelchair" icon, so "wheelchair"
// maps to Accessibility instead. Anything unmapped falls back to ClipboardList.
const ICON_MAP: Record<string, LucideIcon> = {
  utensils: Utensils,
  droplet: Droplet,
  toilet: Toilet,
  wheelchair: Accessibility,
  stethoscope: Stethoscope,
  "message-circle": MessageCircle,
  heart: Heart,
  moon: Moon,
  settings: Settings,
  activity: Activity,
  shield: Shield,
};

export function careIconFor(icon: string | null | undefined): LucideIcon {
  if (!icon) return ClipboardList;
  return ICON_MAP[icon] ?? ClipboardList;
}
