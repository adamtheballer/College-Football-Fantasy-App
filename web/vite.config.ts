import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react-swc";
import path from "path";

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? "http://api:8000";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  root: __dirname,
  server: {
    host: "::",
    port: 8080,
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
