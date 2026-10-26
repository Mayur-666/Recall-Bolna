import { expect, test } from "@playwright/test";

import { login } from "./helpers";

test.skip(!process.env.DEMO_PASSWORD, "DEMO_PASSWORD not set");

test("Ask page shows the orb, the memory field and call history", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Ask Recall" }).first().click();
  await expect(page.getByRole("heading", { name: /talk to recall/i })).toBeVisible();
  await expect(page.getByRole("button", { name: "Talk to Recall" })).toBeVisible();
  await expect(page.getByRole("img", { name: /memory field/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Past calls" })).toBeVisible();
});

test("starting a call without Bolna configured shows the backend's exact reason (real backend, no fake)", async ({ page }) => {
  test.skip(process.env.BOLNA_CONFIGURED === "1", "Bolna is configured; this checks the unconfigured path");
  await login(page);
  await page.goto("/ask");
  await page.getByRole("button", { name: "Talk to Recall" }).click();
  const alert = page.getByRole("alert").filter({ hasText: /BOLNA_API_KEY|BOLNA_AGENT_ID|Bolna/ });
  await expect(alert).toBeVisible();
  await expect(alert).toContainText("bolna-setup");
  await expect(page.getByTestId("orb-state")).toHaveText(/error/i);
});

test("phone fallback validates the number before calling", async ({ page }) => {
  await login(page);
  await page.goto("/ask");
  await page.getByText("Call my phone instead").click();
  await page.getByLabel("Phone number").fill("98765 43210");
  await page.getByRole("button", { name: "Call me" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /E\.164|\+/ })).toBeVisible();
});
