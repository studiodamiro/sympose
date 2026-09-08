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
    // Build straight into the Python package so `pipx install git+…` ships the
    // dashboard (ADR-079). `sympose/webui/` is committed; CI fails if it drifts
    // from a fresh build. `emptyOutDir` is required for an out-of-root target.
    outDir: path.resolve(import.meta.dirname, "../sympose/webui"),
    emptyOutDir: true,
  },
  server: {
    // Proxy API traffic to the FastAPI process (sympose/server.py) so
    // `npm run dev` on :5173 can talk to real endpoints without CORS.
    // Defaults to the TLS dashboard (ADR-064.2 self-signed cert); `secure:
    // false` accepts that cert. Override the target with `SYMPOSE_API_URL`
    // when the workspace opted the dashboard into plain HTTP.
    proxy: Object.fromEntries(
      ["/api", "/health", "/docs"].map((p) => [
        p,
        {
          target: process.env.SYMPOSE_API_URL ?? "https://127.0.0.1:8000",
          secure: false,
          changeOrigin: true,
        },
      ])
    ),
  },
})
