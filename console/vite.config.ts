import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // .wgsl shaders are imported as raw strings.
  assetsInclude: ["**/*.wgsl"],
  server: {
    proxy: {
      "/api": "http://localhost:8787",
    },
  },
});
