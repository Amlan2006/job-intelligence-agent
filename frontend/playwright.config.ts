import { defineConfig, devices } from "@playwright/test";
const port = process.env.E2E_PORT || "3000";
const baseURL =
  process.env.E2E_BASE_URL ||
  `http://${process.env.E2E_HOST || "127.0.0.1"}:${port}`;
export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  timeout: 30_000,
  use: { baseURL, trace: "retain-on-failure" },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1050 },
      },
    },
  ],
  webServer: {
    command: `npm run dev -- --port ${port}`,
    url: baseURL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
