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
    // Proxy API traffic to the FastAPI process (sympose/server.py on :8000)
    // so `npm run dev` on :5173 can talk to real endpoints without CORS.
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/docs": "http://localhost:8000",
    },
  },
})
