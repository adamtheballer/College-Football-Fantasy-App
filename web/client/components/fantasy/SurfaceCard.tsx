import * as React from "react";
import type { VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import { surfaceCardVariants } from "./designSystem";

export interface SurfaceCardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof surfaceCardVariants> {}

export const SurfaceCard = React.forwardRef<HTMLDivElement, SurfaceCardProps>(
  ({ className, variant, padding, ...props }, ref) => (
    <section
      ref={ref}
      className={cn(surfaceCardVariants({ variant, padding }), className)}
      {...props}
    />
  ),
);

SurfaceCard.displayName = "SurfaceCard";
