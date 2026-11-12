import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      // main.tsx is the 3-line React bootstrap; test helpers are not product code.
      exclude: ["src/main.tsx", "src/setupTests.ts", "src/testFixtures.ts", "src/**/*.test.tsx", "src/vite-env.d.ts"],
      reporter: ["text"],
    },
  },
});
