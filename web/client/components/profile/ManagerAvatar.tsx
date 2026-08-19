import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const sizeClasses = {
  xs: "h-6 w-6 text-[8px]",
  sm: "h-8 w-8 text-[10px]",
  md: "h-10 w-10 text-xs",
  lg: "h-14 w-14 text-sm",
  xl: "h-20 w-20 text-xl",
} as const;

export type ManagerAvatarProps = {
  avatarUrl?: string | null;
  managerName?: string | null;
  username?: string | null;
  size?: keyof typeof sizeClasses;
  className?: string;
  eager?: boolean;
  onImageError?: () => void;
  onImageLoad?: () => void;
};

export function managerInitials(managerName?: string | null, username?: string | null): string {
  const value = managerName?.trim() || username?.trim() || "";
  if (!value) return "?";
  const words = value.split(/\s+/).filter(Boolean);
  if (words.length > 1) return words.slice(0, 2).map((word) => word[0]).join("").toUpperCase();
  return value.slice(0, 2).toUpperCase();
}

export function ManagerAvatar({
  avatarUrl,
  managerName,
  username,
  size = "md",
  className,
  eager = false,
  onImageError,
  onImageLoad,
}: ManagerAvatarProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  useEffect(() => {
    setImageFailed(false);
    setImageLoaded(false);
  }, [avatarUrl]);

  const initials = managerInitials(managerName, username);
  const alt = managerName?.trim() || username?.trim()
    ? `${managerName?.trim() || username?.trim()} profile picture`
    : "Manager profile picture";
  // The mobile picker turns a chosen photo into a compact data URL before it
  // reaches this component. It is already locally available, so do not hide
  // it behind another image-load event; doing so causes a visible initials
  // flash and can make the preview appear delayed on mobile Safari.
  const isPreparedLocalPhoto = Boolean(avatarUrl?.startsWith("data:image/"));
  const showImage = Boolean(avatarUrl && !imageFailed && (imageLoaded || isPreparedLocalPhoto));

  return (
    <span
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-white/15 bg-primary/15 font-black uppercase text-primary",
        sizeClasses[size],
        className,
      )}
      aria-label={showImage ? alt : `${managerName?.trim() || username?.trim() || "Manager"} initials ${initials}`}
    >
      <span className={cn("absolute inset-0 flex items-center justify-center", showImage && "opacity-0")}>{initials}</span>
      {avatarUrl && !imageFailed ? (
        <img
          src={avatarUrl}
          alt={alt}
          loading={eager || isPreparedLocalPhoto ? "eager" : "lazy"}
          referrerPolicy="no-referrer"
          className={cn("absolute inset-0 h-full w-full object-cover transition-opacity", showImage ? "opacity-100" : "opacity-0")}
          onLoad={() => {
            setImageLoaded(true);
            onImageLoad?.();
          }}
          onError={() => {
            setImageFailed(true);
            setImageLoaded(false);
            onImageError?.();
          }}
        />
      ) : null}
    </span>
  );
}
