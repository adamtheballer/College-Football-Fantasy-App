import React, { useMemo, useState } from "react";
import { Plus, UserPlus, ArrowRightLeft, UserRoundSearch } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";

type QuickAction = {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
  styleClass: string;
};

export function FloatingQuickActions() {
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  const actions = useMemo<QuickAction[]>(
    () => [
      {
        label: "Add Player",
        icon: UserPlus,
        onClick: () => navigate("/waiver-wire"),
        styleClass: "from-primary/90 to-blue-500/90",
      },
      {
        label: "Propose Trade",
        icon: ArrowRightLeft,
        onClick: () => navigate("/leagues"),
        styleClass: "from-emerald-500/90 to-teal-500/90",
      },
      {
        label: "Player Compare",
        icon: UserRoundSearch,
        onClick: () => navigate("/stats/players"),
        styleClass: "from-amber-500/90 to-orange-500/90",
      },
    ],
    [navigate]
  );

  const hiddenRoutes = ["/login", "/signup"];
  if (!isLoggedIn || hiddenRoutes.includes(location.pathname)) {
    return null;
  }

  return (
    <div className="fixed bottom-8 right-8 z-[180] flex flex-col items-end gap-3">
      <div
        className={cn(
          "flex flex-col items-end gap-3 transition-all duration-300",
          open ? "opacity-100 translate-y-0 pointer-events-auto" : "opacity-0 translate-y-2 pointer-events-none"
        )}
      >
        {actions.map((action) => (
          <button
            key={action.label}
            onClick={() => {
              setOpen(false);
              action.onClick();
            }}
            className={cn(
              "h-12 px-5 rounded-2xl border border-white/15 text-white text-[10px] font-black uppercase tracking-[0.2em] shadow-2xl",
              "bg-gradient-to-r hover:scale-105 transition-transform flex items-center gap-2",
              action.styleClass
            )}
          >
            <action.icon className="w-4 h-4" />
            {action.label}
          </button>
        ))}
      </div>

      <button
        aria-label="Quick actions"
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          "h-14 w-14 rounded-2xl border border-white/20 shadow-[0_20px_40px_rgba(0,0,0,0.35)]",
          "bg-gradient-to-r from-primary to-blue-500 text-white flex items-center justify-center",
          "hover:scale-105 transition-transform"
        )}
      >
        <Plus className={cn("w-5 h-5 transition-transform", open ? "rotate-45" : "rotate-0")} />
      </button>
    </div>
  );
}
