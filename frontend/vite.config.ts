import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Dev: /api is proxied to the FastAPI server so no CORS setup is needed locally.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": { target: env.VITE_PROXY_TARGET || "http://127.0.0.1:8000", changeOrigin: true } },
    },
  };
});
