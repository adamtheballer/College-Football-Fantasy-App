type AppBrandLockupProps = {
  variant: "compact" | "desktop";
};

/** Shared product identity for both shells; only their proportions differ. */
export function AppBrandLockup({ variant }: AppBrandLockupProps) {
  const isDesktop = variant === "desktop";

  return (
    <img
      src="/brand/cffb-logo.png"
      alt="CFFB — College Fantasy Football"
      className={isDesktop ? "h-12 w-auto rounded-lg" : "h-9 w-auto rounded-md"}
    />
  );
}
