type AppBrandLockupProps = {
  variant: "compact" | "desktop";
};

/** Shared product identity for both shells; only their proportions differ. */
export function AppBrandLockup({ variant }: AppBrandLockupProps) {
  const isDesktop = variant === "desktop";

  return (
    <>
      <span className="relative flex leading-none">
        <span
          className={
            isDesktop
              ? "font-display text-[1.75rem] font-black uppercase italic tracking-[-0.08em] text-cfb-text-primary transition group-hover:text-white"
              : "font-display text-lg font-black uppercase italic tracking-[-0.06em] text-cfb-text-primary"
          }
        >
          CFFB
        </span>
      </span>
    </>
  );
}
