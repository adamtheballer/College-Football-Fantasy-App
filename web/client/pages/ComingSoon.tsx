import { CircleUserRound, Handshake, Smartphone, Sparkles } from "lucide-react";

import { SurfaceCard } from "@/components/fantasy";

const roadmap = [
  {
    title: "CFB Fantasy App",
    description:
      "The CFB Fantasy app is coming soon to the App Store, so you can manage your league from your phone.",
    icon: Smartphone,
  },
  {
    title: "Player Headshots",
    description:
      "Recognizable player imagery throughout the app when the approved player-image program is ready.",
    icon: CircleUserRound,
  },
  {
    title: "Player Profiles & History",
    description:
      "A deeper player view that tracks your history drafting, starting, adding, and trading each player.",
    icon: Sparkles,
  },
  {
    title: "Sponsored Deals",
    description:
      "In-app partner offers and discount-code rewards, including Saturday Pick 6 promotions on the Home dashboard.",
    icon: Handshake,
  },
];

export default function ComingSoon() {
  return (
    <div className="mx-auto max-w-5xl space-y-7 pb-20 pt-5">
      <section className="relative overflow-hidden rounded-[2rem] border border-cfb-brand/35 bg-cfb-surface-raised p-7 shadow-[0_0_52px_rgba(37,99,235,0.12)] sm:p-10">
        <div
          aria-hidden="true"
          className="absolute -right-16 -top-20 h-56 w-80 rotate-[-18deg] rounded-full bg-cfb-pink/20 blur-3xl"
        />
        <div className="relative max-w-2xl">
          <p className="cfb-micro-label text-cfb-brand">
            College Football Fantasy
          </p>
          <h1 className="mt-3 cfb-display-title text-4xl sm:text-5xl">
            Coming Soon
          </h1>
          <p className="mt-4 text-base font-semibold leading-7 text-cfb-text-secondary sm:text-lg">
            A look at what we are building next. Saturday Pick 6 is available
            from the Home dashboard.
          </p>
        </div>
      </section>

      <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {roadmap.map(({ title, description, icon: Icon }) => (
          <SurfaceCard
            key={title}
            variant="default"
            padding="default"
            className="min-h-56"
          >
            <Icon className="h-7 w-7 text-cfb-brand" aria-hidden="true" />
            <h2 className="mt-6 text-xl font-black text-cfb-text-primary">
              {title}
            </h2>
            <p className="mt-3 font-medium leading-6 text-cfb-text-secondary">
              {description}
            </p>
          </SurfaceCard>
        ))}
      </section>
    </div>
  );
}
