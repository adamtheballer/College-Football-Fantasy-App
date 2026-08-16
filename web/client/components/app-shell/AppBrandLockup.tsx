type AppBrandLockupProps = {
  variant: "compact" | "desktop";
};

/**
 * Shared release identity for both shells. The desktop sidebar and compact
 * header intentionally say the same thing; only their proportions differ.
 */
export function AppBrandLockup({ variant }: AppBrandLockupProps) {
  const isDesktop = variant === "desktop";

  return (
    <>
      <span className="relative flex flex-col gap-0.5 leading-none">
        <span
          className={
            isDesktop
              ? "text-[10px] font-black uppercase tracking-[0.22em] text-cfb-gold/90"
              : "text-[8px] font-black uppercase tracking-[0.2em] text-cfb-gold/90"
          }
        >
          Early Access
        </span>
        <span className="flex items-center gap-1.5 whitespace-nowrap">
          <span
            className={
              isDesktop
                ? "font-display text-[1.75rem] font-black uppercase italic tracking-[-0.08em] text-cfb-text-primary transition group-hover:text-white"
                : "font-display text-lg font-black uppercase italic tracking-[-0.06em] text-cfb-text-primary"
            }
          >
            CFB Fantasy
          </span>
          <span
            className={
              isDesktop
                ? "rounded-md border border-cfb-brand/50 bg-cfb-brand/[0.12] px-2 py-1 text-[8px] font-black uppercase tracking-[0.14em] text-cfb-cyan"
                : "rounded-md border border-cfb-brand/50 bg-cfb-brand/[0.12] px-1.5 py-0.5 text-[7px] font-black uppercase tracking-[0.14em] text-cfb-cyan"
            }
          >
            Beta
          </span>
        </span>
      </span>
    </>
  );
}
