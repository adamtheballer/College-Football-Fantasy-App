import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { formatTradeError } from "./Trade";

describe("formatTradeError", () => {
  it("shows a permission detail returned by a trade mutation", () => {
    expect(formatTradeError(new ApiError(403, "Only the receiving manager can accept this trade."), "Fallback")).toBe(
      "Only the receiving manager can accept this trade."
    );
  });

  it("shows a lifecycle-conflict detail returned by a trade mutation", () => {
    expect(formatTradeError(new ApiError(409, "This trade is already cancelled."), "Fallback")).toBe(
      "This trade is already cancelled."
    );
  });
});
