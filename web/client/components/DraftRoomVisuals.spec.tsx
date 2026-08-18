// @vitest-environment jsdom

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { collegiateCanvasBackground } from "@/components/BackgroundEffects";
import { DraftRoomVisuals, draftRoomCanvasBackground } from "./DraftRoomVisuals";

describe("DraftRoomVisuals", () => {
  it("uses the same neutral shared canvas as the app shell", () => {
    const { container } = render(<DraftRoomVisuals />);
    const canvas = container.querySelector("[data-draft-room-canvas='true']");

    expect(canvas?.getAttribute("style")).toContain(collegiateCanvasBackground);
    expect(draftRoomCanvasBackground).toBe(collegiateCanvasBackground);
  });
});
