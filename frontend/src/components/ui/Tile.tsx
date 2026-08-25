import { clsx } from "clsx";
import type { ComponentType, ReactNode } from "react";

// Accepts icons from either lucide-react or @carelens/icons -- both are components
// that take at least a className, which is all this renders them with.
type TileIcon = ComponentType<{ className?: string }>;

interface TileProps {
  label: string;
  icon?: TileIcon;
  selected?: boolean;
  alert?: boolean;
  size?: "md" | "sm";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
}

export function Tile({ label, icon: Icon, selected, alert, size = "md", disabled, onClick, className }: TileProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={selected}
      className={clsx(
        "flex aspect-square flex-col items-center justify-center gap-1.5 rounded-xl border text-center transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "md" ? "p-3" : "p-2",
        selected
          ? "border-brand-500 bg-brand-50 text-brand-900 shadow-sm"
          : "border-slate-200 bg-white text-slate-700 hover:border-brand-300 hover:bg-brand-50/40",
        alert && selected && "ring-2 ring-amber-400",
        className,
      )}
    >
      {Icon && <Icon className={size === "md" ? "h-10 w-10" : "h-6 w-6"} />}
      <span className={clsx("leading-tight font-medium", size === "md" ? "text-xs" : "text-[11px]")}>{label}</span>
    </button>
  );
}

export function TileGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx("grid grid-cols-3 gap-2.5 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10", className)}>
      {children}
    </div>
  );
}
