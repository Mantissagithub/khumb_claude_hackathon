import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
// Admin-only preview — isolates the /admin surface so the in-progress public/
// build breakage doesn't block previewing. Run:
//   npx vite --config vite.preview.admin.config.js
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  optimizeDeps: { entries: ["__admin_preview.html"] },
  server: { port: 5199 },
})
