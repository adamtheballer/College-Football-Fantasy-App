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
