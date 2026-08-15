interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_BETA_ACCESS_ENABLED?: string;
  readonly VITE_GIT_BRANCH?: string;
  readonly VITE_GIT_SHA?: string;
  /** Public OneSignal web application identifier; never a provider API key. */
  readonly VITE_ONESIGNAL_APP_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
