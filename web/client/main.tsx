import { createRoot, Root } from "react-dom/client";
import App from "./App";
import { registerNativeDeepLinks } from "./lib/native-deep-links";

void registerNativeDeepLinks();
void import("./lib/push-notifications").then(({ initializeNativePush }) => initializeNativePush()).catch(() => { /* Settings exposes native configuration errors. */ });

const container = document.getElementById("root");
if (container) {
  // Using a global variable to store the root to avoid "container has already been passed to createRoot()" warning in dev
  let root = (window as any)._reactRoot as Root | undefined;
  if (!root) {
    root = createRoot(container);
    (window as any)._reactRoot = root;
  }
  root.render(<App />);
}
