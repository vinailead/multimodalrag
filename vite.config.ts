import { defineConfig } from "vite";

export default defineConfig({
  root: "ui/web",
  build: {
    outDir: "../../dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    root: ".",
    environment: "jsdom",
    include: ["ui/web/src/__tests__/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      include: ["ui/web/src/**/*.ts"],
      exclude: ["ui/web/src/__tests__/**", "ui/web/src/main.ts", "ui/web/src/types.ts"],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,
      },
    },
  },
});
