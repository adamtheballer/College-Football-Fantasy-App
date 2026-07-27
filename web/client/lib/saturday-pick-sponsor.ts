type SaturdayPickSponsor = {
  name: string;
  logo_url?: string | null;
} | null | undefined;

export const WEST_GEORGIA_CORNHOLE_NAME = "West Georgia Cornhole";
const WEST_GEORGIA_CORNHOLE_LOGO = "/west-georgia-cornhole.png";

export const isWestGeorgiaCornhole = (name: string | null | undefined) =>
  String(name ?? "").trim().toLocaleLowerCase() === WEST_GEORGIA_CORNHOLE_NAME.toLocaleLowerCase();

export const getSaturdayPickSponsorLogo = (sponsor: SaturdayPickSponsor) => {
  if (sponsor?.logo_url) return sponsor.logo_url;
  return isWestGeorgiaCornhole(sponsor?.name) ? WEST_GEORGIA_CORNHOLE_LOGO : null;
};

export const getSaturdayPickRewardMessage = (sponsor: SaturdayPickSponsor) =>
  isWestGeorgiaCornhole(sponsor?.name)
    ? "Pick the winner to earn a West Georgia Cornhole discount code."
    : "Pick the winner to compete for this week’s sponsor reward.";
