import { expect, test } from "@playwright/test";

import { deleteConversationsMatching, login } from "./helpers";

test.skip(!process.env.DEMO_PASSWORD, "DEMO_PASSWORD not set");

function transcript(tag: string) {
  return [
    `Asha: For the ${tag} launch, should we send the newsletter on Tuesday or Thursday?`,
    "Mayur: Thursday gets better open rates.",
    `Asha: Okay, let's go with Thursday for the ${tag} newsletter.`,
    "Mayur: I will draft the copy by Wednesday.",
  ].join("\n");
}

test("add conversation, watch it process, see a decision with highlighted evidence", async ({ page }) => {
  test.setTimeout(180_000);
  const tag = `e2e-${Date.now()}`;
  await login(page);
  await page.getByRole("link", { name: "Conversations" }).click();
  await page.getByRole("button", { name: "Add conversation" }).click();
  await page.getByLabel("Title").fill(`Newsletter timing ${tag}`);
  await page.getByLabel("Date").fill("2026-10-21");
  await page.getByLabel("Participants").fill("Asha, Mayur");
  await page.getByLabel("Transcript").fill(transcript(tag));
  await page.getByLabel("Which participant is you?").selectOption("Mayur");
  await page.getByRole("button", { name: "Save conversation" }).click();

  const row = page.getByRole("row", { name: new RegExp(`Newsletter timing ${tag}`) });
  await expect(row).toBeVisible();
  await expect(row.getByText(/queued|processing|ready/)).toBeVisible();
  await expect(row.getByText("ready")).toBeVisible({ timeout: 150_000 });

  await row.getByRole("link", { name: new RegExp(`Newsletter timing ${tag}`) }).click();
  await expect(page.getByRole("heading", { name: `Newsletter timing ${tag}` })).toBeVisible();
  const decisions = page.getByTestId("decisions");
  await expect(decisions).toContainText(/Thursday/i);
  await decisions.getByRole("button", { name: /show in transcript/i }).first().click();
  await expect(page.locator("mark.evidence.active")).toBeVisible();
  await expect(page.locator("mark.evidence").first()).toContainText(/Thursday|draft/i);
  await deleteConversationsMatching(page, tag);
});

test("pasting the same transcript again shows Already added", async ({ page }) => {
  const tag = `dup-${Date.now()}`;
  await login(page);
  await page.goto("/conversations");
  for (let i = 0; i < 2; i++) {
    await page.getByRole("button", { name: "Add conversation" }).click();
    await page.getByLabel("Title").fill(`Dup ${tag} ${i}`);
    await page.getByLabel("Date").fill("2026-10-21");
    await page.getByLabel("Transcript").fill(transcript(tag));
    await page.getByRole("button", { name: "Save conversation" }).click();
  }
  await expect(page.getByRole("alert").filter({ hasText: "Already added" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open the existing conversation" })).toBeVisible();
  await deleteConversationsMatching(page, tag);
});

test("search box shows evidence cards with source and date", async ({ page }) => {
  await login(page);
  await page.goto("/conversations");
  await page.getByPlaceholder("Search your memories").fill("What did Priya say about WebSockets?");
  await page.getByRole("button", { name: "Search" }).click();
  const card = page.getByTestId("evidence-card").first();
  await expect(card).toContainText("API design sync");
  await expect(card).toContainText(/WebSockets/);
});
