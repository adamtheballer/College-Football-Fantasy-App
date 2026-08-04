type SaturdayPickSponsor = {
  name: string;
  logo_url?: string | null;
} | null | undefined;

export const saturdayPick6Sponsor = {
  name: "West Georgia Cornhole",
  logo_url: "/assets/west-georgia-cornhole.png",
  tagline: "#1 in All Things Cornhole & Outdoor Games",
  code: "CFBFAN",
  offer_text: "Use code CFBFAN for 10% off sitewide",
  url: null,
} as const;

export const getSaturdayPickSponsorLogo = (sponsor: SaturdayPickSponsor) => {
  return sponsor?.logo_url ?? null;
};

export const getSaturdayPickRewardMessage = (_sponsor: SaturdayPickSponsor) =>
  "Pick the winner and follow your call through final scoring.";
