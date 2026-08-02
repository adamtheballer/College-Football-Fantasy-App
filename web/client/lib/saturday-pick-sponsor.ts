type SaturdayPickSponsor = {
  name: string;
  logo_url?: string | null;
} | null | undefined;

export const getSaturdayPickSponsorLogo = (sponsor: SaturdayPickSponsor) => {
  return sponsor?.logo_url ?? null;
};

export const getSaturdayPickRewardMessage = (_sponsor: SaturdayPickSponsor) =>
  "Pick the winner and follow your call through final scoring.";
