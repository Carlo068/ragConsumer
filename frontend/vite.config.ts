import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from "@tailwindcss/vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // Native fs-change events from a Windows host don't reliably propagate
    // through a Docker Desktop bind mount into the Linux container, so
    // Vite's default watcher never sees edits -- only enabled inside the
    // dev container (docker-compose.dev.yml sets this), not for a native
    // `npm run dev` on the host, where polling would just waste CPU.
    watch: {
      usePolling: process.env.VITE_USE_POLLING === "true",
    },
  },
})
