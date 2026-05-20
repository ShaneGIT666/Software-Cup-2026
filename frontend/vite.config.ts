import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  root: ".",
  build: {
    outDir: "dist",
    emptyOutDir: true
  },
  plugins: [vue()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/uploads": "http://127.0.0.1:8000"
    }
  }
});
