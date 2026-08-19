// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ManagerAvatar, managerInitials } from "./ManagerAvatar";

afterEach(cleanup);

describe("ManagerAvatar", () => {
  it("uses deterministic initials when no image is present", () => {
    render(<ManagerAvatar managerName="Adam Bajdechi" />);
    expect(screen.getByLabelText(/initials AB/i)).toBeTruthy();
    expect(managerInitials("adamtheballer")).toBe("AD");
  });

  it("falls back to initials when an external image fails", () => {
    render(<ManagerAvatar avatarUrl="https://images.example.com/broken.jpg" managerName="Adam Bajdechi" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByLabelText(/initials AB/i)).toBeTruthy();
  });

  it("shows a prepared mobile photo immediately before the browser emits a load event", () => {
    render(<ManagerAvatar avatarUrl="data:image/jpeg;base64,/9j/4AAQ" managerName="Adam Bajdechi" />);

    expect(screen.getByLabelText("Adam Bajdechi profile picture")).toBeTruthy();
    expect(screen.getByRole("img").className).toContain("opacity-100");
  });
});
