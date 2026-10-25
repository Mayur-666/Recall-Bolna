import { expect, type Page } from "@playwright/test";

export const EMAIL = process.env.DEMO_EMAIL ?? "demo@recall.local";
export const PASSWORD = process.env.DEMO_PASSWORD ?? "";

export async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

/** Delete conversations created by a test so the demo account stays clean. */
export async function deleteConversationsMatching(page: Page, needle: string) {
  const res = await page.request.get(`/api/v1/conversations?q=${encodeURIComponent(needle)}`);
  if (!res.ok()) return;
  for (const c of (await res.json()) as { id: string; title: string }[]) {
    if (c.title.includes(needle)) await page.request.delete(`/api/v1/conversations/${c.id}`);
  }
}
