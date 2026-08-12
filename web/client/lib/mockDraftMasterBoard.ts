import type { Player } from "@/types/player";

export function mergeMockDraftMasterBoardPlayers(
  existingPlayers: Player[],
): Player[] {
  // The approved spreadsheet-backed API pool is the only source of mock-draft
  // players. CFB 27 ratings are trade-value inputs; they must never fabricate
  // board entries or overwrite the spreadsheet's projection/ranking fields.
  return existingPlayers;
}
