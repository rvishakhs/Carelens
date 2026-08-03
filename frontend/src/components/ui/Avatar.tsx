import { clsx } from "clsx";

const sizeClasses = {
  sm: "h-8 w-8 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-16 w-16 text-lg",
};

export function Avatar({
  initials,
  colorClass = "bg-brand-200 text-brand-900",
  size = "md",
  className,
}: {
  initials: string;
  colorClass?: string;
  size?: keyof typeof sizeClasses;
  className?: string;
}) {
  return (
    <div className={clsx("flex shrink-0 items-center justify-center rounded-full font-semibold", sizeClasses[size], colorClass, className)}>
      {initials}
    </div>
  );
}
