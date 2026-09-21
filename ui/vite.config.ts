import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    // Build straight into the Python package so an install ships the
    // dashboard. `sympose/webui/` is committed. `emptyOutDir` is required
    // for an out-of-root target.
    outDir: path.resolve(import.meta.dirname, "../sympose/webui"),
    emptyOutDir: true,
  },
  server: {
    // Proxy API traffic to the FastAPI process (sympose/server.py) so
    // `npm run dev` on :5173 can talk to real endpoints without CORS.
    // Plain HTTP, matching the backend's local-dev-only posture (no TLS,
    // no auth). Override the target with `SYMPOSE_API_URL` if that changes.
    proxy: Object.fromEntries(
      ["/api", "/health", "/docs"].map((p) => [
        p,
        {
          target: process.env.SYMPOSE_API_URL ?? "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      ])
    ),
  },
})
