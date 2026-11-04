import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "uv run uvicorn insurance_mmrag.api.main:app --host 127.0.0.1 --port 8000",
    url: "http://127.0.0.1:8000/api/v1/health",
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
});
