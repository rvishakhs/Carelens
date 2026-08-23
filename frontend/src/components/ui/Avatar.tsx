import { clsx } from "clsx";
import { useState } from "react";

const sizeClasses = {
  sm: "h-8 w-8 text-xs",
  md: "h-10 w-10 text-sm",
  lg: "h-16 w-16 text-lg",
  xl: "h-24 w-24 text-2xl",
};

export function Avatar({
  initials,
  photoUrl,
  colorClass = "bg-brand-200 text-brand-900",
  size = "md",
  className,
}: {
  initials: string;
  photoUrl?: string | null;
  colorClass?: string;
  size?: keyof typeof sizeClasses;
  className?: string;
}) {
  const [imageFailed, setImageFailed] = useState(false);

  if (photoUrl && !imageFailed) {
    return (
      <img
        src={photoUrl}
        alt={initials}
        onError={() => setImageFailed(true)}
        className={clsx("shrink-0 rounded-full object-cover", sizeClasses[size], className)}
      />
    );
  }

  return (
    <div className={clsx("flex shrink-0 items-center justify-center rounded-full font-semibold", sizeClasses[size], colorClass, className)}>
      {initials}
    </div>
  );
}
