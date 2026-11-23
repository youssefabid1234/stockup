import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// One .env for the whole kit: read the repo root's (real env vars still win).
const ROOT = fileURLToPath(new URL("../..", import.meta.url));

export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, ROOT, ""), ...process.env };
  const API = env.VITE_API_TARGET || `http://localhost:${env.API_PORT || 4000}`;
  const AI = env.VITE_AI_TARGET || `http://localhost:${env.AI_PORT || 4100}`;
  const port = Number(env.WEB_PORT || 5173);

  return {
    envDir: ROOT,
    plugins: [react()],
    resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
    server: {
      port,
      strictPort: true,
      host: env.WEB_HOST || "localhost", // 0.0.0.0 in Docker
      // Docker Desktop bind mounts don't always forward file events: poll there.
      watch: env.CHOKIDAR_USEPOLLING === "true" ? { usePolling: true, interval: 300 } : undefined,
      proxy: {
        "/api": { target: API, changeOrigin: true },
        // WebSocket voice channel: /ai/voice → ws://<ai>/voice (listed before /ai so it matches first)
        "/ai/voice": { target: AI.replace(/^http/, "ws"), ws: true, changeOrigin: true, rewrite: (p) => p.replace(/^\/ai/, "") },
        "/ai": { target: AI, changeOrigin: true, rewrite: (p) => p.replace(/^\/ai/, "") },
      },
    },
    preview: { port, strictPort: true, host: env.WEB_HOST || "localhost" },
  };
});
