import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  server: {
    host: "127.0.0.1",
    port: 3000,
    proxy: {
      "/agent-api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/agent-api/, ""),
      },
    },
  },
  preview: { host: "127.0.0.1", port: 3000 },
});
