// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TeamRosterRail } from "./LeagueRoster";

describe("TeamRosterRail", () => {
  it("renders a manager profile photo instead of initials when the roster payload includes one", () => {
    render(
      <TeamRosterRail
        teams={[
          {
            team: {
              id: 1,
              name: "Adam's Team",
              owner_user_id: 42,
              owner_name: "Adam",
              owner_avatar_url: "data:image/jpeg;base64,avatar",
              record: "0-0-0",
            },
            roster: [],
          },
          {
            team: {
              id: 2,
              name: "Emily's Team",
              owner_user_id: 43,
              owner_name: "Emily",
              owner_avatar_url: null,
              record: "0-0-0",
            },
            roster: [],
          },
        ]}
        selectedTeamId={1}
        ownedTeamId={1}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByAltText("Adam profile picture").getAttribute("src")).toBe(
      "data:image/jpeg;base64,avatar",
    );
    expect(screen.getByLabelText("Emily initials EM")).toBeTruthy();
  });
});
