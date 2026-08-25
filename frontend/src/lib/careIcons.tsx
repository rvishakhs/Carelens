import { careIcons, type CareIconName } from "@carelens/icons";
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
import type { ComponentType } from "react";

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

/** A care icon component can come from either lucide-react or @carelens/icons --
 * both accept at least `className`, which is all Tile.tsx actually uses. */
export type CareTemplateIcon = ComponentType<{ className?: string }>;

// @carelens/icons currently only covers Nutrition & Hydration and Personal Care
// (per its own generated icon set) -- template names that slugify cleanly (e.g.
// "Breakfast" -> "breakfast", "Tea (drink)" -> "tea-drink") resolve automatically;
// the couple of names that don't (the package's "makeup" has no hyphen, and
// "Nutrition Review" has no dedicated icon of its own) are listed explicitly.
const TEMPLATE_ICON_OVERRIDES: Partial<Record<string, CareIconName>> = {
  "Make-up": "makeup",
  "Nutrition Review": "nutrition",
};

function slugifyTemplateName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[()]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Per-template icon from the installed @carelens/icons pack, e.g. for "Breakfast"
 * or "Denture Care". Returns undefined for templates the pack doesn't cover yet
 * (every category besides Nutrition & Hydration / Personal Care) -- callers should
 * fall back to rendering the label alone in that case, same as before this pack
 * existed. */
export function careTemplateIconFor(templateName: string): CareTemplateIcon | undefined {
  const override = TEMPLATE_ICON_OVERRIDES[templateName];
  if (override) return careIcons[override];
  const slug = slugifyTemplateName(templateName) as CareIconName;
  return careIcons[slug];
}
