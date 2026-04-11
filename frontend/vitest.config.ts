import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    include: ["**/*.{test,spec}.{ts,tsx}"],
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
    testTimeout: 15_000,
    restoreMocks: true,
    setupFiles: ["./test/setup.ts"],
  },
});

