import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Local dashboard dev server. Requests to /api are proxied to the SIN node's
// local HTTP server (default port 8009) so the SPA can talk to it without CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8009",
    },
  },
});
