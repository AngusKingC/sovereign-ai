import { test, expect } from "@playwright/test";

test("status bar renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("status-bar")).toBeVisible();
  await expect(page.getByText(/Sovereign/)).toBeVisible();
});

test("sidebar has 7 nav items + 2 drawer buttons", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("sidebar")).toBeVisible();
  await expect(page.getByText("Home")).toBeVisible();
  await expect(page.getByText("Tasks")).toBeVisible();
  await expect(page.getByText("Workers")).toBeVisible();
  await expect(page.getByText("Approvals")).toBeVisible();
  await expect(page.getByText("Costs")).toBeVisible();
  await expect(page.getByText("Tools")).toBeVisible();
  await expect(page.getByText("Help")).toBeVisible();
  await expect(page.getByText("Memory")).toBeVisible();
  await expect(page.getByText("Settings")).toBeVisible();
});

test("sidebar click changes view", async ({ page }) => {
  await page.goto("/");
  const tasksButton = page.getByRole("button", { name: "Tasks" });
  await tasksButton.click();
  // Verify view changed - check for tasks panel
  await expect(page.getByTestId("tasks-panel")).toBeVisible();
});

test("bottom bar has activation grid", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("bottom-bar")).toBeVisible();
  await expect(page.getByText("Activation grid")).toBeVisible();
});
