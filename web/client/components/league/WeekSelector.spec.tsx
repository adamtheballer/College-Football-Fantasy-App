// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WeekSelector } from "./WeekSelector";

afterEach(cleanup);

describe("WeekSelector", () => {
  it("uses compact accessible arrows to move between weeks", () => {
    const onChange = vi.fn();
    render(<WeekSelector week={4} selectedWeek={4} onChange={onChange} />);

    expect(screen.queryByText("Prev")).toBeNull();
    expect(screen.queryByText("Next")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Previous week" }));
    fireEvent.click(screen.getByRole("button", { name: "Next week" }));

    expect(onChange).toHaveBeenNthCalledWith(1, 3);
    expect(onChange).toHaveBeenNthCalledWith(2, 5);
  });

  it("disables the previous arrow at week one", () => {
    render(<WeekSelector week={1} selectedWeek={1} onChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Previous week" })).toHaveProperty("disabled", true);
  });
});
