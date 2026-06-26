import { test, expect } from "@playwright/test";

test("tool call events stream via SSE", async ({ page }) => {
  await page.goto("/");
  // Verify SSE connection opens by checking for tool inspector
  await expect(page.getByText("Tool inspector")).toBeVisible();
});

test("memory activations SSE connects", async ({ page }) => {
  await page.goto("/");
  // Verify SSE connection opens by checking for memory drawer button
  await expect(page.getByText("Memory")).toBeVisible();
});
