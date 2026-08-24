// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  confirmPasswordReset: vi.fn(),
  validatePasswordReset: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => auth,
}));

import ResetPassword from "./ResetPassword";

describe("ResetPassword", () => {
  beforeEach(() => {
    auth.confirmPasswordReset.mockReset();
    auth.validatePasswordReset.mockReset();
    auth.validatePasswordReset.mockResolvedValue(true);
  });

  afterEach(cleanup);

  it("updates each password requirement live and only enables submission when every rule passes", async () => {
    render(
      <MemoryRouter initialEntries={["/reset-password?token=valid-reset-token"]}>
        <ResetPassword />
      </MemoryRouter>,
    );

    await screen.findByLabelText("New password");

    const submission = screen.getByRole("button", { name: "Create new password" });
    expect(submission.getAttribute("disabled")).not.toBeNull();
    expect(screen.getByText("One uppercase letter").closest("li")?.dataset.valid).toBe("false");
    expect(screen.getByText("Passwords match").closest("li")?.dataset.valid).toBe("false");

    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "StrongPass123!" } });

    expect(screen.getByText("12+ characters").closest("li")?.dataset.valid).toBe("true");
    expect(screen.getByText("One uppercase letter").closest("li")?.dataset.valid).toBe("true");
    expect(screen.getByText("One number").closest("li")?.dataset.valid).toBe("true");
    expect(screen.getByText("One special character").closest("li")?.dataset.valid).toBe("true");
    expect(submission.getAttribute("disabled")).not.toBeNull();

    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "StrongPass123!" } });

    await waitFor(() => expect(screen.getByText("Passwords match").closest("li")?.dataset.valid).toBe("true"));
    expect(submission.getAttribute("disabled")).toBeNull();
  });
});
