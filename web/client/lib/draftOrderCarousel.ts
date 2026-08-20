export const FIRST_CENTERED_DRAFT_PICK = 4;

export type DraftOrderCarouselScrollInput = {
  overallPick: number;
  cardOffsetLeft: number;
  cardWidth: number;
  containerWidth: number;
};

export const getCenteredDraftOrderScrollLeft = ({
  overallPick,
  cardOffsetLeft,
  cardWidth,
  containerWidth,
}: DraftOrderCarouselScrollInput) => {
  if (overallPick < FIRST_CENTERED_DRAFT_PICK) return 0;
  return Math.max(0, cardOffsetLeft - containerWidth / 2 + cardWidth / 2);
};

const DRAFT_NAME_SUFFIXES = new Set(["jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"]);
const DRAFT_SURNAME_PREFIXES = new Set(["da", "de", "del", "der", "di", "la", "le", "st", "st.", "van", "von"]);

/**
 * Keep the completed-pick label compact without losing the player's identity.
 * Suffixes and common multi-word surname prefixes stay attached to the surname.
 */
export const getDraftedPlayerLastName = (fullName: string | null | undefined) => {
  const parts = fullName?.trim().split(/\s+/).filter(Boolean) ?? [];
  if (parts.length === 0) return null;
  if (parts.length === 1) return parts[0];

  const lastPart = parts[parts.length - 1];
  const hasSuffix = DRAFT_NAME_SUFFIXES.has(lastPart.toLowerCase());
  const surnameEnd = hasSuffix ? parts.length - 2 : parts.length - 1;
  const surnameStart =
    surnameEnd > 0 && DRAFT_SURNAME_PREFIXES.has(parts[surnameEnd - 1].toLowerCase())
      ? surnameEnd - 1
      : surnameEnd;

  const surname = parts.slice(surnameStart, hasSuffix ? undefined : surnameEnd + 1).join(" ");
  const firstInitial = parts[0].replace(/\./g, "").charAt(0).toUpperCase();

  return firstInitial ? `${firstInitial}. ${surname}` : surname;
};

/** Shows a compact, stable avatar for human managers when no image is supplied. */
export const getDraftManagerInitials = (name: string | null | undefined, fallback = "M") => {
  const words = name?.trim().split(/\s+/).filter(Boolean) ?? [];
  if (words.length === 0) return fallback;
  if (words.length === 1) return words[0][0].toUpperCase();
  return `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase();
};
