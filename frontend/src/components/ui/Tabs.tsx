import { clsx } from "clsx";

export function Tabs({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
  className?: string;
}) {
  return (
    <div className={clsx("flex gap-1 overflow-x-auto border-b border-slate-200 scrollbar-none", className)}>
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          className={clsx(
            "relative shrink-0 px-4 py-2.5 text-sm font-medium transition-colors",
            active === tab ? "text-brand-700" : "text-slate-500 hover:text-slate-700",
          )}
        >
          {tab}
          {active === tab && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand-600" />}
        </button>
      ))}
    </div>
  );
}
