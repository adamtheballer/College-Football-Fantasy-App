type SaturdayPickSponsor = {
  name: string;
  logo_url?: string | null;
  offer_text?: string | null;
} | null | undefined;

export const saturdayPick6Sponsor = {
  name: "West Georgia Cornhole",
  logo_url: "/assets/west-georgia-cornhole.png",
  tagline: "#1 in All Things Cornhole & Outdoor Games",
} as const;

export const getSaturdayPickSponsorBranding = (sponsor: SaturdayPickSponsor) => {
  return {
    name: sponsor?.name ?? saturdayPick6Sponsor.name,
    logo_url: sponsor?.logo_url ?? saturdayPick6Sponsor.logo_url,
    tagline: sponsor?.offer_text ?? saturdayPick6Sponsor.tagline,
  };
};

export const getSaturdayPickSponsorLogo = (sponsor: SaturdayPickSponsor) =>
  getSaturdayPickSponsorBranding(sponsor).logo_url;

export const getSaturdayPickRewardMessage = (_sponsor: SaturdayPickSponsor) =>
  "Pick the winner and follow your call through final scoring.";
