export type RuntimeIdentity = {
  git_sha: string;
  git_branch: string;
  runtime_id?: string | null;
  api_process_instance_uuid: string;
  web_git_sha: string;
  worker_git_sha: string;
};

export const WEB_BUILD_SHA = import.meta.env.VITE_GIT_SHA || "unknown";

export const runtimeCompatibilityError = (runtime: RuntimeIdentity): string | null => {
  const required = [runtime.git_sha, runtime.web_git_sha, runtime.worker_git_sha];
  if (required.some((value) => !value || value === "unknown")) {
    return "The release runtime did not provide complete build identity information.";
  }
  if (new Set(required).size !== 1) {
    return "The API, web, and worker build identities do not match.";
  }
  if (WEB_BUILD_SHA !== "unknown" && WEB_BUILD_SHA !== runtime.git_sha) {
    return "The page bundle does not match the running API release.";
  }
  return null;
};
