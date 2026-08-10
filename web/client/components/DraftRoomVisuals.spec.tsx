// @vitest-environment jsdom

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { collegiateCanvasBackground } from "@/components/BackgroundEffects";
import { DraftRoomVisuals, draftRoomCanvasBackground } from "./DraftRoomVisuals";

describe("DraftRoomVisuals", () => {
  it("uses the same collegiate navy, blue, and gold canvas as the app shell", () => {
    const { container } = render(<DraftRoomVisuals />);
    const canvas = container.querySelector("[data-draft-room-canvas='true']");

    expect(canvas?.getAttribute("style")).toContain("rgb(2, 6, 17)");
    expect(canvas?.getAttribute("style")).toContain("rgba(251, 191, 36, 0.14)");
    expect(draftRoomCanvasBackground).toBe(collegiateCanvasBackground);
  });
});
