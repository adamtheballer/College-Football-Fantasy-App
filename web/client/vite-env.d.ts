interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_BETA_ACCESS_ENABLED?: string;
  readonly VITE_GIT_BRANCH?: string;
  readonly VITE_GIT_SHA?: string;
  readonly VITE_PRIVACY_POLICY_URL?: string;
  readonly VITE_PROVIDER_DISCLOSURE_URL?: string;
  readonly VITE_SUPPORT_EMAIL?: string;
  readonly VITE_TERMS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
