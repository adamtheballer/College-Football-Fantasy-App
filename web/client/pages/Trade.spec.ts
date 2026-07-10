import { describe, expect, it } from "vitest";

import { canSendTradeOffer, tradeSelectionSignature } from "./Trade";

describe("trade offer send gating", () => {
  it("keeps send disabled until analysis matches the current selection", () => {
    const originalSignature = tradeSelectionSignature(1, 2, [10], [20]);
    const changedSignature = tradeSelectionSignature(1, 2, [10, 11], [20]);
    const analysis = { give_value: 12, receive_value: 14, delta: 2, verdict: "Slight Win" };

    expect(canSendTradeOffer(null, null, originalSignature, false)).toBe(false);
    expect(canSendTradeOffer(analysis, originalSignature, originalSignature, false)).toBe(true);
    expect(canSendTradeOffer(analysis, originalSignature, changedSignature, false)).toBe(false);
    expect(canSendTradeOffer(analysis, originalSignature, originalSignature, true)).toBe(false);
  });

  it("normalizes selected player order in the analysis signature", () => {
    expect(tradeSelectionSignature(1, 2, [11, 10], [21, 20])).toBe(
      tradeSelectionSignature(1, 2, [10, 11], [20, 21])
    );
  });
});
