import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
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
    port: 5173,
    proxy: {
      // PLAN.md: frontend calls /api/... and Vite forwards to FastAPI :8000 (kills CORS)
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
