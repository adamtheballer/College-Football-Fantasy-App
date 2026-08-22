import type { CapacitorConfig } from "@capacitor/cli";

// This project packages the canonical Vite/React output.  It deliberately
// does not point at a hosted URL: iOS ships the same reviewed bundle as the
// website, while API calls target the production API directly at build time.
const config: CapacitorConfig = {
  appId: "org.collegefantasyfootball.app",
  appName: "College Fantasy Football",
  webDir: "dist/spa",
  ios: {
    // Let OneSignal receive APNs callbacks without competing with Capacitor's
    // default notification delegate.
    handleApplicationNotifications: false,
  },
};

export default config;
