export type SaturdayPickSponsor = {
  name: string;
  logo_url?: string | null;
  offer_text?: string | null;
  terms?: string | null;
  reward_unlocked?: boolean;
  code?: string | null;
  url?: string | null;
};

export const WEST_GEORGIA_CORNHOLE_NAME = "West Georgia Cornhole";
export const WEST_GEORGIA_CORNHOLE_URL = "https://westgeorgiacornhole.com/";
export const WEST_GEORGIA_CORNHOLE_LOGO = "/west-georgia-cornhole.png";
export const WEST_GEORGIA_CORNHOLE_OFFER =
  "Pick the winner to earn a West Georgia Cornhole discount code.";

export const westGeorgiaCornholeSponsor: SaturdayPickSponsor = {
  name: WEST_GEORGIA_CORNHOLE_NAME,
  logo_url: WEST_GEORGIA_CORNHOLE_LOGO,
  offer_text: WEST_GEORGIA_CORNHOLE_OFFER,
  url: WEST_GEORGIA_CORNHOLE_URL,
};

export const getSaturdayPickSponsorUrl = (sponsor?: SaturdayPickSponsor | null) =>
  sponsor?.url?.trim() || WEST_GEORGIA_CORNHOLE_URL;

export const getSaturdayPickSponsorLogo = (sponsor?: SaturdayPickSponsor | null) =>
  sponsor?.logo_url?.trim() || WEST_GEORGIA_CORNHOLE_LOGO;
