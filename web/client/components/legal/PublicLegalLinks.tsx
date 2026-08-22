import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

type PublicLegalLinksProps = {
  className?: string;
};

/** A compact, first-party legal navigation used on public surfaces. */
export function PublicLegalLinks({ className }: PublicLegalLinksProps) {
  return (
    <nav aria-label="Legal information" className={cn("flex flex-wrap items-center justify-center gap-x-3 gap-y-2", className)}>
      <Link to="/privacy" className="transition-colors hover:text-cfb-text-primary">
        Privacy
      </Link>
      <span aria-hidden="true">·</span>
      <Link to="/terms" className="transition-colors hover:text-cfb-text-primary">
        Terms
      </Link>
    </nav>
  );
}
