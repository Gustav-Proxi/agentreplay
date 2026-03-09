import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:7474",
    },
  },
  build: {
    outDir: "../agentreplay/ui_dist",
    emptyOutDir: true,
  },
});
