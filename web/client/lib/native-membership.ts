import {
  Capacitor,
  registerPlugin,
  type PluginListenerHandle,
} from "@capacitor/core";
export type StoreTransaction = {
  signedTransaction: string;
  transactionId: string;
  appAccountToken: string;
};
type NativeStore = {
  product(input: {
    productId: string;
  }): Promise<{ displayPrice: string; displayName: string }>;
  purchase(input: {
    productId: string;
    appAccountToken: string;
  }): Promise<{
    status: "purchased" | "cancelled" | "pending";
    transaction?: StoreTransaction;
  }>;
  restore(input: {
    productId: string;
    appAccountToken: string;
    synchronize: boolean;
  }): Promise<{ transactions: StoreTransaction[] }>;
  finish(input: { transactionId: string }): Promise<void>;
  manage(): Promise<void>;
  addListener(
    event: "transactionUpdated",
    handler: (tx: StoreTransaction) => void,
  ): Promise<PluginListenerHandle>;
};
export const nativeMembership = registerPlugin<NativeStore>("ProMembership");
export const isNativeMembership = () =>
  Capacitor.getPlatform() === "ios" && Capacitor.isNativePlatform();
