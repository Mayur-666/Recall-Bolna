import { expect, test } from "@playwright/test";

import { EMAIL, PASSWORD, login } from "./helpers";

test("unauthenticated visit redirects to login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Sign in to Recall" })).toBeVisible();
});

test("wrong password shows an error and stays on login", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill("definitely-wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Invalid email or password" })).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("login and see dashboard", async ({ page }) => {
  test.skip(!PASSWORD, "DEMO_PASSWORD not set");
  await login(page);
  const conversations = page.getByTestId("stat-conversations");
  await expect(conversations).toBeVisible();
  expect(Number(await conversations.textContent())).toBeGreaterThan(0);
  await expect(page.getByRole("heading", { name: "Recent decisions" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ask Recall" })).toBeVisible();
});
