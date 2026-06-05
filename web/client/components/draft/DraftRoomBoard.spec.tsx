import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DraftRoomBoard } from "./DraftRoomBoard";
import type { DraftBoardState } from "@/types/draft-board";

const baseState: DraftBoardState = {
  mode: "single_mock",
  title: "Single-Player Mock Draft",
  subtitle: "Round 1 • Pick 1 • Overall 1/156",
  status: "live",
  currentOverallPick: 1,
  totalPicks: 156,
  currentRound: 1,
  currentRoundPick: 1,
  currentParticipantName: "Adam",
  currentParticipantType: "human",
  currentTeamName: "Adam's Team",
  secondsRemaining: 30,
  formattedTime: "00:30",
  isUserOnClock: true,
  isComplete: false,
  participants: [
    { id: 1, name: "Adam", teamName: "Adam's Team", participantType: "human", userId: 7, draftPosition: 1, isCurrent: true, isUser: true },
    { id: 2, name: "CPU 2", teamName: "CPU 2", participantType: "bot", userId: null, draftPosition: 2, isCurrent: false, isUser: false },
  ],
  picks: [],
  userRoster: [
    {
      id: 99,
      overallPick: 1,
      roundNumber: 1,
      roundPick: 1,
      participantId: 1,
      participantName: "Adam",
      teamName: "Adam's Team",
      playerId: 11,
      playerName: "Bryant Wesco Jr.",
      playerPosition: "WR",
      playerSchool: "Clemson",
      pickSource: "human",
      createdAt: new Date().toISOString(),
    },
  ],
  rosters: [
    {
      participantId: 1,
      participantName: "Adam",
      teamName: "Adam's Team",
      picks: [
        {
          id: 99,
          overallPick: 1,
          roundNumber: 1,
          roundPick: 1,
          participantId: 1,
          participantName: "Adam",
          teamName: "Adam's Team",
          playerId: 11,
          playerName: "Bryant Wesco Jr.",
          playerPosition: "WR",
          playerSchool: "Clemson",
          pickSource: "human",
          createdAt: new Date().toISOString(),
        },
      ],
    },
  ],
  availablePlayers: [
    { id: 10, rank: 1, name: "Cam Cook", school: "West Virginia", position: "RB", projection: 332, adp: 4 },
  ],
};

const renderBoard = (state: DraftBoardState, options: { completionChoiceMade?: boolean } = {}) =>
  renderToStaticMarkup(
    <DraftRoomBoard
      state={state}
      searchQuery=""
      onSearchChange={() => undefined}
      onDraftPlayer={() => undefined}
      draftPending={false}
      autoPickPending={false}
      showCompletionModal={state.isComplete}
      completionChoiceMade={options.completionChoiceMade}
      onSkipEmail={() => undefined}
      onEmailHistory={() => undefined}
      onExit={() => undefined}
      onReset={() => undefined}
    />
  );

describe("DraftRoomBoard shared layout", () => {
  it("renders the required full-board test ids for single-player mock drafts", () => {
    const html = renderBoard(baseState);

    expect(html).toContain('data-testid="draft-room-board"');
    expect(html).toContain('data-testid="draft-status-header"');
    expect(html).toContain('data-testid="draft-timer"');
    expect(html).toContain('data-testid="draft-order-panel"');
    expect(html).toContain('data-testid="available-players-table"');
    expect(html).toContain('data-testid="draft-player-row"');
    expect(html).toContain("Single-Player Mock Draft");
    expect(html).toContain("Cam Cook");
    expect(html).toContain("Queue");
    expect(html).toContain("Roster");
    expect(html).toContain("History");
  });

  it("renders the same core layout for multiplayer mock drafts", () => {
    const multiplayerState: DraftBoardState = {
      ...baseState,
      mode: "multiplayer_mock",
      title: "Multiplayer Mock Draft",
      currentParticipantName: "Taylor",
      currentTeamName: "Taylor's Team",
      participants: baseState.participants.map((participant) => ({ ...participant, isCurrent: participant.id === 2 })),
    };

    const html = renderBoard(multiplayerState);

    expect(html).toContain('data-testid="draft-room-board"');
    expect(html).toContain('data-testid="draft-status-header"');
    expect(html).toContain('data-testid="draft-timer"');
    expect(html).toContain('data-testid="draft-order-panel"');
    expect(html).toContain('data-testid="available-players-table"');
    expect(html).toContain('data-testid="draft-player-row"');
    expect(html).toContain("Multiplayer Mock Draft");
  });

  it("renders the shared completion modal test id", () => {
    const html = renderBoard({ ...baseState, isComplete: true, status: "completed" }, { completionChoiceMade: true });

    expect(html).toContain('data-testid="draft-complete-modal"');
    expect(html).toContain("Restart Mock");
  });
});
