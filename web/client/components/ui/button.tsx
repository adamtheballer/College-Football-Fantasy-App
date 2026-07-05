import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-2xl text-sm font-semibold ring-offset-background transition-all duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-slate-950 shadow-[0_12px_34px_rgba(14,165,233,0.28)] hover:brightness-110 hover:shadow-[0_16px_42px_rgba(14,165,233,0.36)]",
        destructive:
          "bg-destructive text-destructive-foreground shadow-[0_10px_24px_rgba(220,38,38,0.2)] hover:bg-destructive/90",
        outline:
          "border border-cyan-100/10 bg-white/[0.065] text-foreground backdrop-blur-md hover:border-cyan-200/30 hover:bg-cyan-300/10 hover:text-cyan-50",
        secondary:
          "bg-gradient-to-r from-slate-800/90 to-blue-950/80 text-secondary-foreground shadow-[0_10px_24px_rgba(8,47,73,0.18)] hover:from-slate-700/90 hover:to-blue-900/80",
        ghost: "text-foreground hover:bg-cyan-300/10 hover:text-cyan-50",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
