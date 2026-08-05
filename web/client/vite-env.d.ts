interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_BETA_ACCESS_ENABLED?: string;
  readonly VITE_GIT_BRANCH?: string;
  readonly VITE_GIT_SHA?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
