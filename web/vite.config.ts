import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react-swc";
import path from "path";

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? "http://api:8000";
const configuredDevPort = Number(process.env.WEB_PORT ?? "8080");
const devServerPort = Number.isInteger(configuredDevPort) && configuredDevPort > 0 ? configuredDevPort : 8080;
const buildSha = process.env.VITE_BUILD_SHA ?? process.env.VERCEL_GIT_COMMIT_SHA ?? process.env.GITHUB_SHA ?? "unknown";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  root: __dirname,
  server: {
    host: "::",
    port: devServerPort,
    allowedHosts: ["web"],
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        rewrite: (requestPath) => requestPath.replace(/^\/api/, ""),
      },
    },
    fs: {
      allow: ["./", "./client", "./shared"],
      deny: [".env", ".env.*", "*.{crt,pem}", "**/.git/**", "server/**"],
    },
  },
  build: {
    outDir: "dist/spa",
  },
  define: {
    "import.meta.env.VITE_BUILD_SHA": JSON.stringify(buildSha),
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./client"),
    },
  },
  test: {
    include: ["client/**/*.spec.ts", "client/**/*.test.ts", "client/**/*.spec.tsx", "client/**/*.test.tsx"],
    exclude: ["**/node_modules/**", "**/dist/**", "**/.worktrees/**"],
  },
}));
