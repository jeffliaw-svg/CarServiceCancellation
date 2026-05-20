import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The front-end calls the API same-origin. In dev, proxy /api to the
// local Python server (python -m server.app). In production, either set
// VITE_API_URL to a remote API, or let the Python server host this build.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
