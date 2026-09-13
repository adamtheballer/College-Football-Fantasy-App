// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePickConfirmation, type ConfirmedDraftPick } from "@/hooks/use-pick-confirmation";
import { PickConfirmationStrip } from "./PickConfirmationStrip";

const own = (number: number): ConfirmedDraftPick => ({ key: `${number}:7`, number, teamId: 1, playerId: 7, name: `Player ${number}`, school: "Ole Miss", position: "RB", auto: false });
function Harness({ picks, complete = false, scope = "test" }: { picks: ConfirmedDraftPick[]; complete?: boolean; scope?: string }) {
  const confirmation = usePickConfirmation(scope, picks, 1);
  return <><PickConfirmationStrip pick={confirmation.pick} onFinish={confirmation.finish} />{complete && !confirmation.pending ? <div role="dialog">Complete</div> : null}</>;
}
beforeEach(() => { vi.useFakeTimers(); sessionStorage.clear(); Object.defineProperty(document, "hidden", { configurable: true, value: false }); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); });
const tick = (ms: number) => act(() => vi.advanceTimersByTime(ms));

describe("confirmed pick presentation", () => {
  it("does not replay initial history, remounts or a different draft baseline", () => {
    const view = render(<Harness picks={[own(1)]} />);
    expect(screen.queryByTestId("pick-confirmation")).toBeNull();
    view.rerender(<Harness picks={[own(1), own(2)]} />);
    expect(screen.getByTestId("pick-confirmation").textContent).toContain("Player 2");
    view.unmount();
    const next = render(<Harness picks={[own(1), own(2)]} />);
    expect(screen.queryByTestId("pick-confirmation")).toBeNull();
    next.rerender(<Harness scope="new-draft" picks={[own(3)]} />);
    expect(screen.queryByTestId("pick-confirmation")).toBeNull();
  });
  it("holds for two full seconds after entry, queues consecutive own picks, then completes", () => {
    const view = render(<Harness picks={[]} />);
    view.rerender(<Harness picks={[own(1), own(2)]} complete />);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByTestId("pick-confirmation").dataset.phase).toBe("enter");
    tick(240);
    expect(screen.getByTestId("pick-confirmation").dataset.phase).toBe("hold");
    tick(1999);
    expect(screen.getByTestId("pick-confirmation").dataset.phase).toBe("hold");
    tick(1);
    expect(screen.getByTestId("pick-confirmation").dataset.phase).toBe("exit");
    tick(240);
    expect(screen.getByTestId("pick-confirmation").textContent).toContain("Player 2");
    tick(2480);
    expect(screen.queryByTestId("pick-confirmation")).toBeNull();
    expect(screen.getByRole("dialog").textContent).toBe("Complete");
    view.rerender(<Harness picks={[own(1), own(2)]} complete />);
    expect(screen.queryByTestId("pick-confirmation")).toBeNull();
  });
  it("ignores opponents, supports auto picks and recovers from a broken portrait", () => {
    const view = render(<Harness picks={[]} />);
    view.rerender(<Harness picks={[{ ...own(1), teamId: 2 }]} />);
    expect(screen.queryByTestId("pick-confirmation")).toBeNull();
    view.rerender(<Harness picks={[{ ...own(1), teamId: 2 }, { ...own(2), auto: true, imageUrl: "/broken.png" }]} />);
    expect(screen.getByRole("status").textContent).toContain("Auto-pick confirmed");
    fireEvent.error(document.querySelector("img")!);
    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("Player 2");
  });
  it("skips suspended celebration and permits completion after backgrounding", () => {
    const view = render(<Harness picks={[]} />);
    view.rerender(<Harness picks={[own(1)]} complete />);
    Object.defineProperty(document, "hidden", { configurable: true, value: true });
    fireEvent(document, new Event("visibilitychange"));
    expect(screen.queryByTestId("pick-confirmation")).toBeNull();
    Object.defineProperty(document, "hidden", { configurable: true, value: false });
    fireEvent(document, new Event("visibilitychange"));
    expect(screen.queryByTestId("pick-confirmation")).toBeNull();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });
  it("keeps the two-second hold with reduced motion, without sliding", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    const view = render(<Harness picks={[]} />);
    view.rerender(<Harness picks={[own(1)]} complete />);
    expect(screen.getByTestId("pick-confirmation").className).not.toContain("animate-pick");
    tick(1999);
    expect(screen.queryByRole("dialog")).toBeNull();
    tick(1);
    expect(screen.getByRole("dialog")).toBeTruthy();
    vi.unstubAllGlobals();
  });
});
