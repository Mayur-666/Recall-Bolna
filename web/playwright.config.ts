import { defineConfig, devices } from "@playwright/test";

// Runs against the real Compose stack (web on :3000, backend, Postgres, Ollama) with the
// seeded demo account. Credentials come from the environment, never from the repo.
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: process.env.E2E_CHANNEL ?? "msedge" } }],
});
